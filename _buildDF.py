import pandas as pd
from pprint import pprint


# (hutches,objtypes) hutchaliases objtypeNames objTypeIDs saveprehooks saveposthooks applyprehooks applyposthooks verbosity loglevel logpath zenity

dCfgData = {'hutch': ['amo', 'sxr', 'xpp', 'xcs', 'cxi', 'mfx', 'mec'],
            'objType': ['ims_motor', 'ims_motor', 'ims_motor', 'ims_motor', 
                        'ims_motor', 'ims_motor', 'ims_motor'],
            'globalMode': ['pmgr', 'pmgr', 'pmgr', 'pmgr', 'pmgr', 'pmgr', 'pmgr'],
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
            'objTypeKeys':[(':MMS:',), 
                           (':MMS:',), 
                           (':MMS:',), 
                           (':MMS:',),
                           (':MMS:',), 
                           (':MMS:',),  
                           (':MMS:',)],
            'objTypeSumFlds':[('FLD_DESC', 'FLD_SN', 'FLD_PN', 'FLD_PORT'),
                              ('FLD_DESC', 'FLD_SN', 'FLD_PN', 'FLD_PORT'),
                              ('FLD_DESC', 'FLD_SN', 'FLD_PN', 'FLD_PORT'),
                              ('FLD_DESC', 'FLD_SN', 'FLD_PN', 'FLD_PORT'),
                              ('FLD_DESC', 'FLD_SN', 'FLD_PN', 'FLD_PORT'),
                              ('FLD_DESC', 'FLD_SN', 'FLD_PN', 'FLD_PORT'),
                              ('FLD_DESC', 'FLD_SN', 'FLD_PN', 'FLD_PORT')],
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
cols = dCfgData.keys()
dCfgDF = pd.DataFrame(dCfgData, columns=cols)
if __name__ == "__main__":
	dCfgDF.to_csv('db/localMode.csv')
