import pandas as pd
from pprint import pprint


# (hutches,objtypes) hutchaliases objtypeNames objTypeIDs saveprehooks saveposthooks applyprehooks applyposthooks verbosity loglevel logpath zenity

dCfgData = {'HutchesObjTypes': [('amo', 'ims_motor'), ('sxr', 'ims_motor'),
                                ('xpp', 'ims_motor'), ('xcs', 'ims_motor'),
                                ('cxi', 'ims_motor'), ('mfx', 'ims_motor'),
                                ('mec', 'ims_motor')],
            'hutchAliases': [('sxd', 'all'), 
                             ('sxd', 'all'), 
                             ('hxd', 'all'), 
                             ('hxd', 'all'), 
                             ('all',), 
                             ('all',), 
                             ('all',)],
            'objTypeNames': ['motor', 'motor', 'motor', 'motor', 'motor', 
                             'motor', 'motor'],
            'objTypeIDs': ['FLD_SN', 'FLD_SN', 'FLD_SN', 'FLD_SN', 'FLD_SN', 
                            'FLD_SN', 'FLD_SN'],
            'objTypeKeys':[(':MMS:',), (':MMS:',), (':MMS:',), (':MMS:',),
                           (':MMS:',), (':MMS:',),  (':MMS:',)],
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
            'verbosity': ['INFO', 'INFO', 'INFO', 'INFO', 'INFO', 'INFO', 'INFO'],
            'logLevel': ['DEBUG', 'DEBUG', 'DEBUG', 'DEBUG', 'DEBUG', 'DEBUG', 
                         'DEBUG'],
            'loggingPath': ['', '', '', '', '', '', ''],
            'zenity': [False, False, False, False, False, False, False]
            }
dCfgDF = pd.DataFrame(dCfgData, columns=['HutchesObjTypes', 'hutchAliases',
                                         'hutchAliases', 'objTypeNames', 
                                         'objTypeIDs', 'savePreHooks', 
                                         'savePostHooks', 'applyPreHooks', 
                                         'applyPostHooks', 'verbosity', 
                                         'logLevel', 'loggingPath', 'zenity'])
if __name__ == "__main__":
	dCfgDF.to_csv('localMode.csv')
