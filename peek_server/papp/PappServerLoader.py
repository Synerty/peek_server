import imp
import logging
import os
import sys
from _collections import defaultdict

from peek_platform.papp.PappLoaderBase import PappLoaderBase
from peek_server.papp.ServerPlatformApi import ServerPlatformApi
from peek_server.server.sw_version.PappSwVersionInfoUtil import getLatestPappVersionInfos
from vortex.PayloadIO import PayloadIO
from vortex.Tuple import removeTuplesForTupleNames, \
    registeredTupleNames, tupleForTupleName


logger = logging.getLogger(__name__)


class PappServerLoader(PappLoaderBase):
    _instance = None

    def __new__(cls, *args, **kwargs):
        assert cls._instance is None, "PappServerLoader is a singleton, don't construct it"
        cls._instance = PappLoaderBase.__new__(cls)
        return cls._instance

    def __init__(self):
        PappLoaderBase.__init__(self)

        from peek_server.PeekServerConfig import peekServerConfig
        self._pappPath = peekServerConfig.pappSoftwarePath

        self._rapuiEndpointInstancesByPappName = defaultdict(list)
        self._rapuiResourcePathsByPappName = defaultdict(list)
        self._rapuiTupleNamesByPappName = defaultdict(list)

    def unloadPapp(self, pappName):
        oldLoadedPapp = self._loadedPapps.get(pappName)

        if not oldLoadedPapp:
            return

        # Remove the Papp resource tree
        from peek_server.backend.SiteRootResource import root as serverRootResource
        serverRootResource.deleteChild(pappName.encode())

        # Remove the registered endpoints
        for endpoint in self._rapuiEndpointInstancesByPappName[pappName]:
            PayloadIO().remove(endpoint)
        del self._rapuiEndpointInstancesByPappName[pappName]

        # Remove the registered tuples
        removeTuplesForTupleNames(self._rapuiTupleNamesByPappName[pappName])
        del self._rapuiTupleNamesByPappName[pappName]

        self._unloadPappPackage(pappName, oldLoadedPapp)

    def _loadPappThrows(self, pappName):
        self.unloadPapp(pappName)

        pappVersionInfo = getLatestPappVersionInfos(name=pappName)
        if not pappVersionInfo:
            logger.warning("Papp version info for %s is missing, loading skipped",
                           pappName)
            return

        pappVersionInfo = pappVersionInfo[0]

        # Make note of the initial registrations for this papp
        endpointInstancesBefore = set(PayloadIO().endpoints)
        tupleNamesBefore = set(registeredTupleNames())

        # Everyone gets their own instance of the papp API
        serverPlatformApi = ServerPlatformApi()

        srcDir = os.path.join(self._pappPath, pappVersionInfo.dirName, 'cpython')
        sys.path.append(srcDir)

        modPath = os.path.join(srcDir, pappName, "PappServerMain.py")
        if not os.path.exists(modPath) and os.path.exists(modPath + "c"):  # .pyc
            PappServerMainMod = imp.load_compiled('%s.PappServerMain' % pappName,
                                                  modPath + 'c')
        else:
            PappServerMainMod = imp.load_source('%s.PappServerMain' % pappName,
                                                modPath)

        pappMain = PappServerMainMod.PappServerMain(serverPlatformApi)

        self._loadedPapps[pappName] = pappMain

        # Configure the celery app in the worker
        # This is not the worker that will be started, it allows the worker to queue tasks

        from peek_platform.CeleryApp import configureCeleryApp
        configureCeleryApp(pappMain.celeryApp)

        pappMain.start()
        sys.path.pop()

        # Add all the resources required to serve the backend site
        # And all the papp custom resources it may create
        from peek_server.backend.SiteRootResource import root as serverRootResource
        serverRootResource.putChild(pappName.encode(), serverPlatformApi.rootResource)

        # Make note of the final registrations for this papp
        self._rapuiEndpointInstancesByPappName[pappName] = list(
            set(PayloadIO().endpoints) - endpointInstancesBefore)

        self._rapuiTupleNamesByPappName[pappName] = list(
            set(registeredTupleNames()) - tupleNamesBefore)

        self.sanityCheckServerPapp(pappName)

    def sanityCheckServerPapp(self, pappName):
        ''' Sanity Check Papp

        This method ensures that all the things registed for this papp are
        prefixed by it's pappName, EG papp_noop
        '''

        # All endpoint filters must have the 'papp' : 'papp_name' in them
        for endpoint in self._rapuiEndpointInstancesByPappName[pappName]:
            filt = endpoint.filt
            if 'papp' not in filt and filt['papp'] != pappName:
                raise Exception("Payload endpoint does not contan 'papp':'%s'\n%s"
                                % (pappName, filt))

        # all tuple names must start with their pappName
        for tupleName in self._rapuiTupleNamesByPappName[pappName]:
            TupleCls = tupleForTupleName(tupleName)
            if not tupleName.startswith(pappName):
                raise Exception("Tuple name does not start with '%s', %s (%s)"
                                % (pappName, tupleName, TupleCls.__name__))

    def notifyOfPappVersionUpdate(self, pappName, pappVersion):
        logger.info("Received PAPP update for %s version %s", pappName, pappVersion)
        return self.loadPapp(pappName)

    def pappAdminTitleUrls(self):
        """ Papp Admin Name Urls

        @:returns a list of tuples (pappName, pappTitle, pappUrl)
        """
        data = []
        for pappName, papp in list(self._loadedPapps.items()):
            data.append((pappName, papp.title, "/%s" % pappName))

        return data

    def pappAdminAngularRoutes(self):
        """ Papp Admin Name Urls

        @:returns a list of tuples (pappName, angularAdminModule)
        """
        data = []
        for pappName, papp in list(self._loadedPapps.items()):
            data.append((pappName, papp.angularAdminModule))

        return data


pappServerLoader = PappServerLoader()
