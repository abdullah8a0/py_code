import numpy as np
from lcobj import TagFinder, TagNotFound, get_coords_from_path
import os
from pathlib import Path
import random

path = Path('/Users/abdullah/Desktop/UROP/Tess/local_code/py_code/transient_data')
transient_tags = [] 
with os.scandir(path / 'transient_lc') as entries:
    for i,entry in enumerate(entries):
        if not entry.name.startswith('.') and entry.is_file():
            if entry.name[:3] != 'lc_':
                continue
            tag = (-1,-1,*map(int,get_coords_from_path(entry.name)))
            transient_tags.append(tag)

#generated_transients = {}
# Remove transients from Renamer insertions.

def get_sector_data(sectors,t,verbose=True):
    assert t in ('scalar','vector','signat')

    if not hasattr(sectors, '__iter__'):
        sectors = [sectors]       

    for sector in sectors:
        sector2 = str(sector) if int(sector) > 9 else '0'+str(sector)
        data_raw =np.genfromtxt(Path(f"Features/{sector2}_{t}.csv"), delimiter=',')
        tags, data = data_raw[::,1:5].astype(int), data_raw[::,5:]
        yield tags,data

class Data: ### -> cam -1
    def __init__(self,sector,default,insert = []) -> None:
        self.sector = sector
        vec = get_sector_data(sector,'vector',verbose=False)
        scal = get_sector_data(sector,'scalar',verbose=False)
        sign = get_sector_data(sector, 'signat', verbose=False)
        self.vtags, self.vdata = next(vec)
        self.stags,self.sdata = next(scal)
        self.signattags,self.signatdata = next(sign)
        self.tagfindscalar = TagFinder(self.stags)
        self.tagfindvector = TagFinder(self.vtags)
        self.tagfindsignat = TagFinder(self.signattags)
        self.transientfind = TagFinder(transient_tags)
        self.default_type = default
        self.ind = insert
        #########################################
        # Get transient data here
        #########################################

        self.scalartran = np.genfromtxt( path /"T_scalar.csv", delimiter=',')[::,5:]
        self.vectortran = np.genfromtxt( path /"T_vector.csv", delimiter=',')[::,5:]
        self.signattran = np.genfromtxt( path /"T_signat.csv", delimiter=',')[::,5:]
    
    def update_insert(self,insert):
        self.ind = np.concatenate((self.ind,insert)).astype('int32')
        return self
    def new_insert(self,insert):
        self.ind = np.array(insert)
        return self

    def lookup_tran(self,tag):
        ind = self.transientfind.find(tag)
        if ind in self.ind:
            return ind
        else:
            raise Exception('Data Finder tried to access a tag the it was not allowed to')


    def get(self,tag,verbose = False, type = None):
        if type is None:
            type =self.default_type
        if tag[0]==-1:
            if type == 'scalar':
                ind = self.transientfind.find(tag)
                if ind in self.ind:
                    return self.scalartran[ind]
                else:
                    raise Exception('Data Finder tried to access a tag the it was not allowed to')
            elif type == 'vector':
                ind = self.transientfind.find(tag)
                if ind in self.ind:
                    return self.vectortran[ind]
                else:
                    raise Exception('Data Finder tried to access a tag the it was not allowed to')
            elif type == 'signat':
                ind = self.transientfind.find(tag)
                if ind in self.ind:
                    return self.signattran[ind]
                else:
                    raise Exception('Data Finder tried to access a tag the it was not allowed to')
            else:
                raise Exception('Wrong type')

        try:
            if type == 'scalar':
                return self.sdata[self.tagfindscalar.find(tag)]
            elif type == 'vector':
                return self.vdata[self.tagfindvector.find(tag)]
            elif type == 'signat':
                return self.signatdata[self.tagfindsignat.find(tag)]
            else:
                raise Exception('Wrong type')
        except TagNotFound:
            print('Tag not in sector')

    def get_all(self, type = None):
        if type is None:
            type = self.default_type
        if type == 'scalar':
            sector_data = self.sdata
            if self.ind !=[]:
                tran_data = self.scalartran[self.ind]##### get transient data ###
            else:
                tran_data = []
            ret = np.concatenate((sector_data,tran_data)) if len(self.ind) != 0 else sector_data
            return ret
        elif type == 'vector':
            sector_data = self.vdata
            if self.ind !=[]:
                tran_data = self.vectortran[self.ind]##### get transient data ###
            else:
                tran_data = []
            ret = np.concatenate((sector_data,tran_data)) if len(self.ind) != 0 else sector_data
            return ret
        elif type == 'signat':
            sector_data = self.signatdata
            if self.ind !=[]:
                tran_data = self.signattran[self.ind]##### get transient data ###
            else:
                tran_data = []
            ret = np.concatenate((sector_data,tran_data)) if len(self.ind) != 0 else sector_data
            return ret
        else:
            raise Exception('Wrong type')
    def get_some(self,tags,type=None):
        if type is None:
            type = self.default_type
        try:
            return np.array([self.get(tag,type=type) for tag in tags])
        except TagNotFound:
            print('Tag not in sector')

    

class AccuracyTest:     # Generative vs Discriminative Model
    def __init__(self, pre_tags) -> None:
        self.tags = pre_tags
    def insert(self,num,seed=None) -> tuple[list[int], list[int]]: #(ind,tags)
        random.seed(seed)
        ind = random.sample(range(len(transient_tags)),num)
        tags = np.array([transient_tags[i] for i in ind])
        return (ind,np.concatenate((self.tags,tags)))

    def measure(self,datafinder : Data,result_tags):
        passed_tags = []
        for tag in result_tags:
            try:
                passed_tags.append(datafinder.lookup_tran(tag))
            except TagNotFound:
                continue
        assert all(ind in datafinder.ind for ind in passed_tags)
        print(f'Retention Accuracy: {round(len(passed_tags)/len(datafinder.ind),4)*100}')

    def test(self,data_api_model:Data=None,target = None,num=10 , trials = 1, seed = None,*args, **kwargs):
        assert target is not None
        random.seed(seed)
        old_ind = data_api_model.ind
        for i in range(trials):
            print(f'Trial {i}/{trials} starting')
            ind,inserted_tags = self.insert(num,seed=random.randint(0,50000))
            data_api_model.update_insert(ind)

            print(f'Insertion finished')
            result_tags = target(tags=inserted_tags,**kwargs)
            print(f'Results calculated')

            self.measure(data_api_model,result_tags)
        post_test = self.clean(result_tags)
        print(f'Reduction {len(self.tags)} -> {len(post_test)} = {round(100*(1-len(post_test)/len(self.tags)),2)}')
        data_api_model.new_insert(old_ind)
        return post_test
    
    def clean(self,post_tags) -> np.ndarray:
        cleaned = post_tags[post_tags[:,0]!=-1] # np.where(post_tags[:,0] == -1,post_tags,np.array([]))
        return cleaned



if __name__ == '__main__':
    data = Data(43,'s')
    model = AccuracyTest(np.array([(1,1,1,1),(1,1,1,2)]))
    ind,tags = model.insert(5)
    print(tags)
    data.new_insert(ind)

    model.measure(data,tags)
    print(model.clean(tags))
    #print(data.get((1,1,110,956)))


    pass


# Current transients: (-1, -1, 622, 1765), (-1, -1, 1620, 691), (-1, -1, 509, 256), (-1, -1, 1054, 824), (-1, -1, 1048, 946), 
# (-1, -1, 216, 2030), (-1, -1, 1192, 466), (-1, -1, 1198, 2009), (-1, -1, 1495, 538), (-1, -1, 2036, 1174), (-1, -1, 1123, 248),
#  (-1, -1, 750, 1023), (-1, -1, 2036, 1776), (-1, -1, 901, 1499), (-1, -1, 1818, 1155), (-1, -1, 337, 1708), (-1, -1, 1109, 1645),
#  (-1, -1, 790, 1522), (-1, -1, 1126, 1469), (-1, -1, 482, 1461), (-1, -1, 297, 1119), (-1, -1, 1525, 2010), (-1, -1, 1353, 1012),
#  (-1, -1, 293, 1788), (-1, -1, 995, 494), (-1, -1, 1297, 904), (-1, -1, 226, 844), (-1, -1, 1650, 793), (-1, -1, 1312, 1886), 
# (-1, -1, 680, 1226), (-1, -1, 648, 240), (-1, -1, 1987, 217), (-1, -1, 967, 1990), (-1, -1, 695, 1608), (-1, -1, 223, 1741), 
# (-1, -1, 574, 1214), (-1, -1, 594, 1233), (-1, -1, 2050, 1286), (-1, -1, 1326, 43), (-1, -1, 1711, 1696), (-1, -1, 1565, 1157), 
# (-1, -1, 489, 1800), (-1, -1, 1281, 547), (-1, -1, 694, 1162), (-1, -1, 1425, 411), (-1, -1, 450, 273), (-1, -1, 93, 1742), 
# (-1, -1, 530, 1110), (-1, -1, 326, 799), (-1, -1, 2062, 648), (-1, -1, 1505, 1708), (-1, -1, 1179, 1104), (-1, -1, 636, 544), 
# (-1, -1, 1584, 1125), (-1, -1, 1039, 1246), (-1, -1, 233, 915), (-1, -1, 68, 690), (-1, -1, 578, 202), (-1, -1, 137, 399), 
# (-1, -1, 111, 1160), (-1, -1, 1940, 1995), (-1, -1, 679, 569), (-1, -1, 1748, 348), (-1, -1, 584, 96), (-1, -1, 103, 1903), 
# (-1, -1, 1953, 1208), (-1, -1, 101, 1641), (-1, -1, 1666, 525), (-1, -1, 123, 1116), (-1, -1, 1130, 754), (-1, -1, 1932, 2015), 
# (-1, -1, 264, 1137), (-1, -1, 1473, 1661), (-1, -1, 1711, 717), (-1, -1, 1903, 1486), (-1, -1, 1877, 1600), (-1, -1, 355, 85), 
# (-1, -1, 1226, 1549), (-1, -1, 558, 1874), (-1, -1, 1985, 623), (-1, -1, 148, 1765), (-1, -1, 195, 1152), (-1, -1, 1720, 1633), 
# (-1, -1, 302, 1055), (-1, -1, 1752, 1579), (-1, -1, 1787, 866), (-1, -1, 243, 494), (-1, -1, 1044, 1626), (-1, -1, 353, 1352), 
# (-1, -1, 251, 1452), (-1, -1, 2020, 945), (-1, -1, 1103, 606), (-1, -1, 1313, 1191), (-1, -1, 840, 1325), (-1, -1, 428, 1609), 
# (-1, -1, 1869, 468), (-1, -1, 939, 1874), (-1, -1, 979, 1740), (-1, -1, 1906, 651), (-1, -1, 2053, 1025), (-1, -1, 1530, 2016), 
# (-1, -1, 634, 631), (-1, -1, 1673, 647), (-1, -1, 1031, 1165), (-1, -1, 1167, 636), (-1, -1, 100, 1095), (-1, -1, 998, 1670), 
# (-1, -1, 489, 2029), (-1, -1, 650, 282), (-1, -1, 1192, 362), (-1, -1, 1645, 1821), (-1, -1, 1127, 1764), (-1, -1, 818, 1372), 
# (-1, -1, 645, 1136), (-1, -1, 1416, 1162), (-1, -1, 1032, 739), (-1, -1, 1554, 939), (-1, -1, 934, 861), (-1, -1, 1637, 688), 
# (-1, -1, 919, 17), (-1, -1, 1193, 1478), (-1, -1, 1178, 2001), (-1, -1, 1618, 991), (-1, -1, 1073, 1668), (-1, -1, 1172, 1321), 
# (-1, -1, 802, 891), (-1, -1, 1778, 738), (-1, -1, 70, 1634), (-1, -1, 1519, 1435), (-1, -1, 2062, 1347), (-1, -1, 972, 726), 
# (-1, -1, 1012, 1400), (-1, -1, 957, 1933)