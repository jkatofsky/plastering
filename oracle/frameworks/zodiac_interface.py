import os 
import sys
import importlib.util
import pdb

from .framework_interface import FrameworkInterface, exec_measurement
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/zodiac')
from ..db import *
from ..common import *

POINT_POSTFIXES = ['sensor', 'setpoint', 'alarm', 'command', 'meter']


from zodiac import Zodiac # This may imply incompatible imports.

class ZodiacInterface(FrameworkInterface):
    """docstring for ZodiacInterface"""
    def __init__(self, building, exp_id='none', conf={'seed_sample_num': 10}):
        """
        rawdata -- containing the entire dataset. ex)
        {
            "building1": {
                "raw_metadata": {
                    "srcid1": "RM-101.ZNT"
                },
            }
        }
                "char_labels": {
                    "srcid1": [("R", "B_Room"), ... ]
                },
                "tagsets": {
                    "srcid1": ["Room", "leftidentifier", 
                               "Zone_Temperature_Sensor"]
                },
                "triples": {
                    "srcid1": [("RM-101.ZNT", RDF.type, "Zone_Temperature_Sensor"),
                               ("RM-101", RDF.type, "

        """
        columns_names = ['VendorGivenName', 
                         'BACnetName', 
                         'BACnetDescription', 
                         'BACnetUnit', 
                         'BACnetTypeStr']
        super(ZodiacInterface, self).__init__(conf, exp_id, 'zodiac')
        
        true_sensor_types = {}
        for labeled in LabeledMetadata.objects:
            tagsets = labeled.tagsets
            if tagsets:
                point_tagset = None
                for tagset in tagsets:
                    if is_point_tagset(tagset):
                        point_tagset = tagset
                        break
                if point_tagset:
                    true_sensor_types[labeled.srcid] = point_tagset

        names = {}
        descs = {}
        type_strs = {}
        types = {}
        jci_names = {}
        units = {}
        for raw_point in RawMetadata.objects:
            srcid = raw_point['srcid']
            if srcid in true_sensor_types:
                self.target_srcids.append(srcid)
                metadata = raw_point['metadata']
                names[srcid] = metadata['BACnetName']
                jci_names[srcid] = metadata['VendorGivenName']
                descs[srcid] = metadata['BACnetDescription']
                type_strs[srcid] = {str(metadata['BACnetTypeStr']): 1}
                types[srcid] = {str(metadata['BACnetTypeStr']): 1}
                units[srcid] = {str(metadata['BACnetUnit']): 1}
        

        conf['n_estimators'] = 400
        conf['random_state'] = 0
        #conf['n_jobs'] = 1
        self.zodiac = Zodiac(names, descs, units, type_strs, types, jci_names, 
                             true_sensor_types, conf=conf)
        self.learned_srcids = set(self.zodiac.learned_srcids)

        self.pred['tagsets'] = dict((srcid, []) 
                                    for srcid in self.target_srcids)
        self.pred['point'] = dict((srcid, None) 
                                    for srcid in self.target_srcids)

    def learn_one_step_auto(self, sample_num):
        new_srcids = zodiac.select_informative_samples(sample_num=10)
        new_labels = []
        for new_srcid in new_srcids:
            labeled = LabeledMetadata.objects(srcid=new_srcid)
            if not labeled:
                raise Exception('Labels do not exist for {0}'.format(new_srcid))
            new_labels.append(labeled)
        self.update_model(new_srcids, new_labels)
        
    def learn_one_step(self, srcids, labeled):
        new_labels = []
        for srcid, one_labeled in zip(srcids, labeled):
            point_tagset = None
            for tagset in one_labeled.tagsets:
                if is_point_tagset(tagset):
                    point_tagset = tagset
                    break
            if not point_tagset:
                raise Exception('Point Tagset not found in labels for {0}'\
                            .format(new_srcid))
            new_labels.append(point_tagset)
        self.zodiac.update_model(new_srcids, new_labels)

    @exec_measurement
    def learn_auto(self):
        num_sensors_in_gray = 10000
        while num_sensors_in_gray > 0:
            new_srcids = self.zodiac.select_informative_samples_only(10)
            self.update_model(new_srcids)
            num_sensors_in_gray = self.zodiac.get_num_sensors_in_gray()
            pred_point_tagsets = self.zodiac.predict(self.target_srcids)
            for i, srcid in enumerate(self.target_srcids):
                self.pred['tagsets'][srcid] = set([pred_point_tagsets[i]])
            print(num_sensors_in_gray)
            self.evaluate()
        pdb.set_trace()


    def update_model_auto(self, new_sample_num):
        """
        # General process
          1. Get most informative samples. 
          2. Register the new samples
          3. Update the model.
          4. Update the inferences.
        """
        pass

    def update_model(self, srcids):
        """
        Same as update_model_auto except 
        that the srcids are externally specified.
        """
        #self.used_srcids = self.used_srcids.union(set(srcids))
        self.learned_srcids = self.learned_srcids.union(set(srcids))
        new_samples = list()
        for srcid in srcids:
            labeled = LabeledMetadata.objects(srcid=srcid)
            if not labeled:
                pdb.set_trace()
                raise Exception('Labels do not exist for {0}'.format(srcid))
            labeled = labeled[0]
            point_tagset = sel_point_tagset(labeled.tagsets)
            if not point_tagset:
                pdb.set_trace()
                raise Exception('Point Tagset not found at {0}'
                                .format(labeled.tagsets))
            new_samples.append(point_tagset)
        self.zodiac.update_model(srcids, new_samples)

        
