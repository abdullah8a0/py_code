import numpy as np
from astropy import stats as astat
import matplotlib.pyplot as plt
import pylab
from scipy import stats,signal
import math
from pathlib import Path
from sklearn.ensemble import IsolationForest


def set_base(loc):
    global base
    base = loc


#working_folder = "C:\\Users\\saba saleemi\\Desktop\\UROP\\TESS\\"

def gen_path(sector,cam,ccd,col,row):
    # Generates path to specific file
    file_name = 'lc_'+str(col)+'.'+str(row)
    cam,ccd,col,row = str(cam),str(ccd),str(col),str(row)

    if -1 in [int(cam),int(ccd),int(sector)] :
        return Path(f'/Users/abdullah/Desktop/UROP/Tess/local_code/py_code/transient_data/transient_lc/lc_{col}.{row}')
        

    ccd_path_raw = ["sector","/cam","_ccd","/lc_transient_pipeline/"]
    sector2 = str(sector) if int(sector) > 9 else '0'+str(sector)

    ccd_path = Path(ccd_path_raw[0]+sector2 + ccd_path_raw[1]+cam+ccd_path_raw[2]+ccd+ccd_path_raw[3])

    try:
        file_path = base / ccd_path / file_name
    except NameError:
        from run_classif import base
        set_base(base)
        file_path = base / ccd_path / file_name
    return file_path

class LCOutOfBoundsError(Exception):
    pass
class LCMissingDataError(Exception):
    pass

class LC(object):
    def __init__(self, sector, cam, ccd, col, row):
        mask = {
            35: (2268.50, 2272.045),
        }
        

        try:
            assert 44 <= int(col) <= 2097
            assert 0 <= int(row) <= 2047 
        except AssertionError:
            raise LCOutOfBoundsError(f'Out of bouds: {col},{row}')

        self.path = gen_path(sector,cam,ccd,col,row)
        self.sector = int(sector)
        self.cam = int(cam)
        self.ccd = int(ccd)
        self.coords = (int(col),int(row))
        lc_data = np.genfromtxt(self.path)

        try:
            assert len(lc_data.shape) == 2
        except AssertionError:
            raise LCMissingDataError("The flux file is almost empty")
        if not np.all(np.isnan(lc_data[0,:])):
            self.flux_unclipped = -lc_data[:, 1]
            self.time_unclipped = lc_data[:, 0]
            self.error_unclipped = lc_data[:, 2]
            self.bg_unclipped = -lc_data[:, 6]
            self.iscleaned = False
        else:
            new_lc = lc_data[1:,:].astype('float64')
            self.flux_unclipped = new_lc[:, 2]
            self.time_unclipped = new_lc[:, 1]
            self.error_unclipped = new_lc[:, 3]
            self.bg_unclipped = new_lc[:, 4]
            self.iscleaned = True
        
        bg_clip = astat.sigma_clip(self.bg_unclipped,sigma=3)

        self.flux = np.array([self.flux_unclipped[i] for i in np.ma.nonzero(bg_clip)[0]]) 
        self.time = np.array([self.time_unclipped[i] for i in np.ma.nonzero(bg_clip)[0]])
        self.error = np.array([self.error_unclipped[i] for i in np.ma.nonzero(bg_clip)[0]])
        self.bg = np.array([self.bg_unclipped[i] for i in np.ma.nonzero(bg_clip)[0]])

        self.error = np.nan_to_num(self.error,nan=100)


        arr_un, unique = np.unique(self.time,return_index=True)
        self.flux = self.flux[unique] 
        self.time  =self.time[unique]        
        self.error =self.error[unique]
        self.bg =   self.bg[unique] 
        if len(self.flux) < 10:
            raise LCMissingDataError("The flux file has less than 10 entries")
        if sector in mask.keys():
            masking_arr = np.logical_or(self.time < mask[sector][0],self.time > mask[sector][1])

            self.flux   = self.flux[masking_arr]
            self.time   = self.time[masking_arr]
            self.error  = self.error[masking_arr]
            self.bg     = self.bg[masking_arr]   


        self.N = len(self.flux)
        self.mean = np.mean(self.flux)
        self.std = np.std(self.flux)

        try:
            assert self.N > 60
        except AssertionError:
            raise LCMissingDataError("The flux file has less than 60 entries")

        # Smoothing using SavGol Filter
        #try:

        #    self.smooth_flux = signal.savgol_filter(self.flux,min((1|int(0.05*self.N),61)), 3)
        #except:
        #    raise LCMissingDataError
        #self.linreg = stats.linregress(self.time,self.flux)[0:3]  #(slope,c,r)

        self.is_padded = False
        self.is_FFT = False         # Flags whether the instance has these attributes
        self.is_percentiles = False  

        self.normed_flux : np.ndarray = (self.flux - min(self.flux))/(np.ptp(self.flux))
        self.normed_time : np.ndarray = (self.time-self.time[0])/np.ptp(self.time)
        #self.normed_smooth_flux : np.ndarray = (self.smooth_flux - min(self.smooth_flux))/np.ptp(self.smooth_flux)

    def plot(self, flux = None, time = None, show_bg = True, show_err = False,show_smooth=False,scatter=[]):
        flux = self.flux if flux is None else flux
        time = self.time if time is None else time

        #fig = pylab.gcf()
        #fig.canvas.manager.set_window_title('Figure_'+str(self.coords[0])+'_'+str(self.coords[1]))
        plt.xlabel("Time (Days)")
        plt.ylabel("Raw Flux")
        plt.scatter(time,flux,s=0.5)
        if show_bg:
            plt.scatter(time,self.bg,s=0.1)
        if show_err:
            plt.errorbar(time, flux, yerr=self.error, fmt ='o' )
        if show_smooth:
            plt.scatter(time,self.smooth_flux,s=0.1)
        for data in scatter:
            try:
                time_s,flux_s = data
                plt.scatter(time_s,flux_s,s=0.1)
            except:
                plt.scatter(time,data,s=0.1)
        plt.show()
        return self

    def remove_outliers_1(self):

        EPSILON = 0.02   
        time = self.normed_time

        flux = self.normed_flux

        groups : dict= {0:{0}}

        block = [(0,time[0],flux[0],0)] #(ind,t,f,g)

        for i,(t,f) in enumerate(zip(time[1:],flux[1:]),1):
            while block and abs(block[0][1]-t)>EPSILON:
                block.pop(0)
            seen_groups =set()
            for i_,t_,f_,g_ in block:
                if abs(f_-f)>2*EPSILON:
                    continue
                seen_groups.add(g_)

            if len(seen_groups)>1:  # combines groups 
                new = set()
                for group in seen_groups:
                    new |= groups[group]
                    del groups[group]
                new.add(i)
                groups[min(seen_groups)] = new
                block = [(ind,i,j,min(seen_groups) if ind in new else k) for ind,i,j,k in block]
                tfgroup = min(seen_groups)
            elif len(seen_groups) == 1:     # adds a to an existing group
                tfgroup = min(seen_groups)
                groups[tfgroup].add(i)
            else:   # creates a new group
                tfgroup = max(groups.keys())+1
                groups[tfgroup] = set([i])

            block.append((i,t,f,tfgroup))
        
        inliers = []
        top = [[0,0],[0,0],[0,0]]
        for group,ind in groups.items():
            if len(ind) > top[0][1]:
                top = [[0,0],top[0],top[1]]
                top[0] = [group,len(ind)]
                continue
            elif len(ind) > top[1][1]:
                top = [top[0],[0,0],top[1]]
                top[1] = [group,len(ind)]
            elif len(ind) > top[2][1]:
                top[2] = [group,len(ind)]
        if top[2][1] > 0.2*top[1][1]:
            inliers = [ind  for i,_ in top for ind in groups[i]]
        else: 
            allowed = [top[0][0],top[1][0]]
            inliers = [ind for i in allowed for ind in groups[i]]
        
        inliers = np.sort(np.array(inliers))
        
        self.flux        = self.flux[inliers]
        self.time        = self.time[inliers]
        self.error       = self.error[inliers]
        self.bg          = self.bg[inliers]
        self.N           = inliers.size
        self.mean        = np.mean(self.flux)
        self.std         = np.std(self.flux)
        self.median      = np.median(self.flux)
        self.normed_flux = (self.flux - min(self.flux))/(np.ptp(self.flux))
        self.normed_time = (self.time-self.time[0])/np.ptp(self.time)


        try: 
            self.smooth_flux = signal.savgol_filter(self.flux,min((1|int(0.05*self.N),61)), 3)
        except:
            raise LCMissingDataError

        if self.N < 60:
            raise LCMissingDataError
        
        self.linreg = stats.linregress(self.time,self.flux)[0:3] 
   
        self.normed_smooth_flux = (self.smooth_flux - min(self.smooth_flux))/np.ptp(self.smooth_flux)
        return self
        pass

    def remove_outliers(self):
        
        self.cross_conflict = 0 # implement a measure of how much 
        #'''
        EPSILON = 0.02   
        time = self.normed_time

        flux = self.normed_flux

        groups : dict= {0:{0}}

        block = [(0,time[0],flux[0],0)] #(ind,t,f,g)

        for i,(t,f) in enumerate(zip(time[1:],flux[1:]),1):
            while block and abs(block[0][1]-t)>EPSILON:
                block.pop(0)
            seen_groups =set()
            for i_,t_,f_,g_ in block:
                if abs(f_-f)>2*EPSILON:
                    continue
                seen_groups.add(g_)

            if len(seen_groups)>1:  # combines groups 
                new = set()
                for group in seen_groups:
                    self.cross_conflict +=1 if len(groups[group]) > 10 else 0
                    new |= groups[group]
                    del groups[group]
                new.add(i)
                groups[min(seen_groups)] = new
                block = [(ind,i,j,min(seen_groups) if ind in new else k) for ind,i,j,k in block]
                tfgroup = min(seen_groups)
            elif len(seen_groups) == 1:     # adds a to an existing group
                tfgroup = min(seen_groups)
                groups[tfgroup].add(i)
            else:   # creates a new group
                tfgroup = max(groups.keys())+1
                groups[tfgroup] = set([i])

            block.append((i,t,f,tfgroup))
        
        inliers = []
        top = [[0,0],[0,0],[0,0]]
        for group,ind in groups.items():
            if len(ind) > top[0][1]:
                top = [[0,0],top[0],top[1]]
                top[0] = [group,len(ind)]
                continue
            elif len(ind) > top[1][1]:
                top = [top[0],[0,0],top[1]]
                top[1] = [group,len(ind)]
            elif len(ind) > top[2][1]:
                top[2] = [group,len(ind)]
        if top[2][1] > 0.2*top[1][1]:
            inliers = [ind  for i,_ in top for ind in groups[i]]
        else: 
            allowed = [top[0][0],top[1][0]]
            inliers = [ind for i in allowed for ind in groups[i]]
        
        inliers = np.sort(np.array(inliers))
        
        self.flux        = self.flux[inliers]
        self.time        = self.time[inliers]
        self.error       = self.error[inliers]
        self.bg          = self.bg[inliers]
        self.N           = inliers.size
        self.mean        = np.mean(self.flux)
        self.std         = np.std(self.flux)
        self.median      = np.median(self.flux)
        self.normed_flux = (self.flux - min(self.flux))/(np.ptp(self.flux))
        self.normed_time = (self.time-self.time[0])/np.ptp(self.time)


        #second

        EPSILON = 0.02   
        time = self.normed_time

        flux = self.normed_flux

        groups : dict= {0:{0}}

        block = [(0,time[0],flux[0],0)] #(ind,t,f,g)

        for i,(t,f) in enumerate(zip(time[1:],flux[1:]),1):
            while block and abs(block[0][1]-t)>EPSILON:
                block.pop(0)
            seen_groups =set()
            for i_,t_,f_,g_ in block:
                if abs(f_-f)>2*EPSILON:
                    continue
                seen_groups.add(g_)

            if len(seen_groups)>1:  # combines groups 
                new = set()
                for group in seen_groups:
                    self.cross_conflict +=1 if len(groups[group]) > 10 else 0
                    new |= groups[group]
                    del groups[group]
                new.add(i)
                groups[min(seen_groups)] = new
                block = [(ind,i,j,min(seen_groups) if ind in new else k) for ind,i,j,k in block]
                tfgroup = min(seen_groups)
            elif len(seen_groups) == 1:     # adds a to an existing group
                tfgroup = min(seen_groups)
                groups[tfgroup].add(i)
            else:   # creates a new group
                tfgroup = max(groups.keys())+1
                groups[tfgroup] = set([i])

            block.append((i,t,f,tfgroup))
        
        inliers = []
        top = [[0,0],[0,0],[0,0]]
        for group,ind in groups.items():
            if len(ind) > top[0][1]:
                top = [[0,0],top[0],top[1]]
                top[0] = [group,len(ind)]
                continue
            elif len(ind) > top[1][1]:
                top = [top[0],[0,0],top[1]]
                top[1] = [group,len(ind)]
            elif len(ind) > top[2][1]:
                top[2] = [group,len(ind)]
        if top[2][1] > 0.2*top[1][1]:
            inliers = [ind  for i,_ in top for ind in groups[i]]
        else: 
            allowed = [top[0][0],top[1][0]]
            inliers = [ind for i in allowed for ind in groups[i]]
        
        inliers = np.sort(np.array(inliers))

        
        self.flux        = self.flux[inliers]
        self.time        = self.time[inliers]
        self.error       = self.error[inliers]
        self.bg          = self.bg[inliers]
        self.N           = inliers.size
        self.mean        = np.mean(self.flux)
        self.std         = np.std(self.flux)
        self.median      = np.median(self.flux)
        self.normed_flux = (self.flux - min(self.flux))/(np.ptp(self.flux))
        self.normed_time = (self.time-self.time[0])/np.ptp(self.time)

        #

        try: 
            self.smooth_flux = signal.savgol_filter(self.flux,min((1|int(0.05*self.N),61)), 3)
        except:
            raise LCMissingDataError

        if self.N < 60:
            raise LCMissingDataError
        
        self.linreg = stats.linregress(self.time,self.flux)[0:3] 
   
        self.normed_smooth_flux = (self.smooth_flux - min(self.smooth_flux))/np.ptp(self.smooth_flux)
        return self
    def make_percentiles(self):
        self.percentiles = {i:np.percentile(self.flux,i) for i in range(0,101,1)}
        self.is_percentiles = True

    def flatten(self, smooth = None):
        flux = self.smooth_flux if smooth is None else self.flux

        fit = signal.savgol_filter(self.flux, 201 , 1)
        self.flat =  flux - fit
        return self

    def pad_flux(self):
        perday = 48 if self.sector <= 26 else 144
        bins = int((self.time[-1] - self.time[0])*perday)
        stat = np.nan_to_num(stats.binned_statistic(self.time, self.normed_flux, bins=bins)[0])

        pow2 = math.ceil(math.log2(len(stat)) + math.log2(6))
        pow2 = 1
        while 2**pow2 < len(stat)*6:
            pow2+=1
        padded_flux = np.zeros(2**pow2)
        padded_flux[0:len(stat)] = stat

        self.padded_flux = padded_flux
        self.is_padded = True
    
    def make_FFT(self):
        assert self.is_padded
        len_fft = len(self.padded_flux)

        fft = np.fft.fft(self.padded_flux)[:len_fft//2]#*1/len_fft

        self.is_FFT = True
        perday = 48 if self.sector <= 26 else 144
        delta_t = 1/perday
        
        freq = np.fft.fftfreq(len_fft, delta_t)[:len_fft//2]
        upper = np.abs(freq - 200).argmin()

        freq_f, fft_f = freq[50:upper], np.abs(fft[50:upper])       # Final results        
        self.fft_freq = (freq_f, fft_f)
        # Top 5 (freq,pow)

        ind = np.argpartition(fft_f, -5)[-5:]
        self.significant_fequencies = np.array(sorted(zip(freq_f[ind], fft_f[ind]), reverse=True, key = lambda elem: elem[1])) 

        T = 1/self.significant_fequencies[0][0]

        phase = self.time - self.time[0]
        for i in range(len(phase)):
            while phase[i] > T:
                phase[i] -= T

        self.phase_space = phase        # Folded time space

    def plot_FFT(self):
        assert self.is_FFT
        freq, pow = self.fft_freq
        plt.scatter(freq,pow,s=5)
        plt.show()        



    def plot_phase(self):
        assert self.is_FFT

        fig = pylab.gcf()
        fig.canvas.manager.set_window_title('Figure_'+str(self.cam)+'_'+str(self.ccd)+'_'+str(self.coords[0])+'_'+str(self.coords[1])+'_Phase(FFT)')
        plt.xlabel("Phase")
        plt.ylabel("True Flux (/10^6)")

        plt.scatter(self.phase_space,self.flux,s=0.5)
        plt.show()

    def smooth_plot(self):
        plt.scatter(np.arange(len(self.smooth_flux)), self.smooth_flux, s=0.5)
        plt.show()

class TagNotFound(Exception):
    pass
class TagFinder:
    def __init__(self,tags_original):

        tags = np.copy(tags_original)

        tags = tags.tolist()
        tags = sorted(enumerate(tags), key =lambda x:x[1])
        map = {i:tags[i][0] for i in range(len(tags))}
        tags = np.array([x[1] for x in tags])                 # reorder feat with tags
        self.tags = tags
        self.map = map
    
    def find(self,tag):
        return self.map[self.bin_search(np.array(tag))]



    def gt(self,x,y):
        return self.lt(y,x)

    def bin_search(self,tag) -> int:
        tags = self.tags
        upper = tags.shape[0]-1
        lower = 0
        while lower <= upper:
            mid = (upper + lower)//2
            if self.lt(tags[mid], tag):
                lower = mid + 1
            elif self.gt(tags[mid] , tag):
                upper = mid - 1
            else:
                return mid
        raise TagNotFound(f"Tag is not in the data : {tuple(tag)}")

    def lt(self,x,y):
        if (x==y).all():
            return False
        idx = np.where((x!=y))[0][0]
        #print(x[idx])
        return x[idx]< y[idx]



def get_coords_from_path(file_path):
    # returns coords from any file path
    file_path = str(file_path)
    i = file_path.rfind('lc_')
    d = file_path.rfind('.')

    x = file_path[i+3:d]
    y = file_path[d+1:]
    return (x,y)
if __name__ == '__main__':
    LC(32,-1,-1,68,690).plot().remove_outliers().plot()
    pass
    #set_base("C:\\Users\\saba saleemi\\Desktop\\UROP\\TESS\\transient_lcs\\unzipped_ccd\\")                 # Change this to the folder where your sxx_transient_lcs is located