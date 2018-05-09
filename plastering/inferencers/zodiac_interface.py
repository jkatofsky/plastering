import os
import sys
import importlib.util
import pdb

from . import Inferencer
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/zodiac')
from ..metadata_interface import *
from ..common import *

POINT_POSTFIXES = ['sensor', 'setpoint', 'alarm', 'command', 'meter']


from zodiac import Zodiac # This may imply incompatible imports.

class ZodiacInterface(Inferencer):

    def __init__(self,
                 target_building,
                 target_srcids,
                 source_buildings=[],
                 ui=None,
                 config={}):
        super(ZodiacInterface, self).__init__(
            target_building=target_building,
            source_buildings=source_buildings,
            target_srcids=target_srcids,
            ui=None,
            required_label_types=[POINT_TAGSET],
            target_label_type=POINT_TAGSET,
            config=config,
            framework_name='zodiac')

        # init config file for Zodiac
        if 'n_estimators' not in config:
            config['n_estimators'] = 400
        if 'random_state' not in config:
            config['random_state'] = 0

        # Init raw data for Zodiac
        names = {}
        descs = {}
        type_strs = {}
        types = {}
        jci_names = {}
        units = {}
        for raw_point in RawMetadata.objects(building=self.target_building):
            srcid = raw_point['srcid']
            if srcid in self.target_srcids:
                metadata = raw_point['metadata']
                if not metadata:
                    raise Exception('Metadata for {0} does not exist'
                                    .format(srcid))
                if 'BACnetName' in metadata:
                    bacnet_name = metadata['BACnetName']
                else:
                    bacnet_name = ''
                names[srcid] = bacnet_name
                if 'VendorGivenName' in metadata:
                    vendor_given_name = metadata['VendorGivenName']
                else:
                    vendor_given_name = ''
                jci_names[srcid] = vendor_given_name
                if 'BACnetDescription' in metadata:
                    bacnet_desc = metadata['BACnetDescription']
                else:
                    bacnet_desc = ''
                descs[srcid] = bacnet_desc

                if 'BACnetTypeStr' in metadata:
                    bacnet_typestr = {metadata['BACnetTypeStr']: 1}
                else:
                    bacnet_typestr = {}
                type_strs[srcid] = bacnet_typestr

                if 'BACnetType' in metadata:
                    bacnet_type = {str(metadata['BACnetType']): 1}
                else:
                    bacnet_type = {}
                types[srcid] = {str(bacnet_type): 1}
                if 'BACnetUnit' in metadata:
                    bacnet_unit = {str(metadata['BACnetUnit']): 1}
                else:
                    bacnet_unit = {}
                units[srcid] = bacnet_unit

        self.zodiac = Zodiac(names, descs, units,
                             type_strs, types, jci_names, [], conf=config)
        if 'seed_srcids' in config:
            seed_srcids = config['seed_srcids']
        else:
            if 'seed_num' in config:
                seed_num = config['seed_num']
            else:
                seed_num = 10
            seed_srcids = self.zodiac.get_random_learning_srcids(seed_num)
        self.update_model(seed_srcids)

    def select_informative_samples(self, sample_num=10):
        return self.zodiac.select_informative_samples_only(sample_num)

    def learn_auto(self):
        num_sensors_in_gray = 10000 # random initial finish confidtion
        while num_sensors_in_gray > 0:
            new_srcids = self.select_informative_samples(10)
            self.update_model(new_srcids)
            num_sensors_in_gray = self.zodiac.get_num_sensors_in_gray()
            #pred_points = self.zodiac.predict(self.target_srcids)
            #for i, srcid in enumerate(self.target_srcids):
            #    self.pred['point'][srcid] = set([pred_points[i]])
            #pred = self.predict(self.target_srcids)
            print(num_sensors_in_gray)
            self.evaluate(self.target_srcids)

    def update_model(self, srcids):
        super(ZodiacInterface, self).update_model(srcids)
        new_samples = list()
        for srcid in srcids:
            labeled = LabeledMetadata.objects(srcid=srcid)
            if not labeled:
                raise Exception('Labels do not exist for {0}'.format(srcid))
            labeled = labeled[0]
            point_tagset = labeled.point_tagset
            if not point_tagset:
                raise Exception('Point Tagset not found at {0}: {1}'
                                .format(srcid, labeled.tagsets))
            new_samples.append(point_tagset)
        self.zodiac.update_model(srcids, new_samples)

    def predict(self, target_srcids=None):
        if not target_srcids:
            target_srcids = self.target_srcids
        super(ZodiacInterface, self).predict(target_srcids)

        pred_g = self._get_empty_graph()
        pred_points = self.zodiac.predict(target_srcids)
        for srcid, pred_point in zip(target_srcids, pred_points):
            self._add_pred_point_result(pred_g, srcid, pred_point)
        return pred_g

    def predict_proba(self, srcids=None):
        if not srcids:
            srcids = self.target_srcids
        super(ZodiacInterface, self).predict_proba(srcids)
        pred_points = self.zodiac.predict(srcids)
        proba_points = self.zodiac.predict_proba(srcids)
        conf_dict = {}
        for srcid, proba, point in \
            zip(srcids, proba_points, pred_points):
            try:
                triple = self._make_instance_tuple(srcid, point)
            except:
                pdb.set_trace()
            conf_dict[triple] = max(proba)
        return conf_dict

    #def update_prior(self, pred_g):
    #    super(ZodiacInterface, self).update_prior(pred_g)

