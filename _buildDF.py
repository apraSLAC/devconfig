import pandas as pd
from pprint import pprint


# (hutches,objtypes) hutchaliases objtypeNames objTypeIDs saveprehooks saveposthooks applyprehooks applyposthooks verbosity loglevel logpath zenity

dCfgData = {'Hutches,ObjTypes': [('amo', 'ims_motor'), ('sxr', 'ims_motor'),
                                 ('xpp', 'ims_motor'), ('xcs', 'ims_motor'),
                                 ('cxi', 'ims_motor'), ('mfx', 'ims_motor'),
                                 ('mec', 'ims_motor')],
            'hutchAliases': ['sxd', 'sxd', 'hxd', 'hxd', '', '', ''],
            'objTypeNames': ['motor', 'motor', 'motor', 'motor', 'motor', 
                             'motor', 'motor'],
            'objTypeIDs': ['FLD_SN', 'FLD_SN', 'FLD_SN', 'FLD_SN', 'FLD_SN', 
                            'FLD_SN', 'FLD_SN'],
            'savePreHooks': ['savePrehooks.ims_motor', 'savePrehooks.ims_motor', 
                             'savePrehooks.ims_motor', 'savePrehooks.ims_motor', 
                             'savePrehooks.ims_motor', 'savePrehooks.ims_motor', 
                             'savePrehooks.ims_motor'],
            'savePostHooks': ['savePostHooks.ims_motor', 'savePostHooks.ims_motor',
                              'savePostHooks.ims_motor', 'savePostHooks.ims_motor',
                              'savePostHooks.ims_motor', 'savePostHooks.ims_motor',
                              'savePostHooks.ims_motor'],
            'applyPreHooks': ['applyPreHooks.ims_motor', 'applyPreHooks.ims_motor', 
                              'applyPreHooks.ims_motor', 'applyPreHooks.ims_motor', 
                              'applyPreHooks.ims_motor', 'applyPreHooks.ims_motor', 
                              'applyPreHooks.ims_motor'],
            'applyPostHooks': ['applyPostHooks.ims_motor', 'applyPostHooks.ims_motor', 
                               'applyPostHooks.ims_motor', 'applyPostHooks.ims_motor', 
                               'applyPostHooks.ims_motor', 'applyPostHooks.ims_motor', 
                               'applyPostHooks.ims_motor'],
            'verbosity': ['low', 'low', 'low', 'low', 'low', 'low', 'low'],
            'logLevel': ['INFO', 'INFO', 'INFO', 'INFO', 'INFO', 'INFO', 'INFO'],
            'loggingPath': ['', '', '', '', '', '', ''],
            'zenity': [False, False, False, False, False, False, False]
            }
dCfgDF = pd.DataFrame(dCfgData, columns=['Hutches,ObjTypes', 'hutchAliases',
                                         'hutchAliases', 'objTypeNames', 
                                         'objTypeIDs', 'savePreHooks', 
                                         'savePostHooks', 'applyPreHooks', 
                                         'applyPostHooks', 'verbosity', 
                                         'logLevel', 'loggingPath', 'zenity'])
if __name__ == "__main__":
	dCfgDF.to_csv('localMode.csv')
