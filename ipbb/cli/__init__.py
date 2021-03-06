from __future__ import print_function

# Import click for ansi colors
import click

from .utils import findFileInParents
from os import walk
from os.path import join, split, exists, splitext, basename
from ..depparser.Pathmaker import Pathmaker
from ..depparser.DepFileParser import DepFileParser

# Constants
kWorkAreaCfgFile = '.ipbbwork'
kProjAreaCfgFile = '.ipbbproj'
kSourceDir = 'src'
kProjDir = 'proj'



# ------------------------------------------------------------------------------
class FolderInfo(object):
    pass
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
class Environment(object):
    """docstring for Environment"""

    _verbosity = 0



    # ----------------------------------------------------------------------------
    def __init__(self):
        super(Environment, self).__init__()

        self._autodetect()
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    def _clear(self):
        self._depParser = None
        # self.workPath = None
        # self.workCfgFile = None

        self.work = FolderInfo()
        self.work.path = None
        self.work.cfgFile = None

        self.currentproj = FolderInfo()
        self.currentproj.name = None
        self.currentproj.path = None
        self.currentproj.file = None
        self.currentproj.config = None
        # self.projectPath = None
        # self.projectFile = None
        # self.projectConfig = None

        self.pathMaker = None
    # ------------------------------------------------------------------------------

    # ----------------------------------------------------------------------------
    def _autodetect(self):

        self._clear()

        lWorkAreaPath = findFileInParents(kWorkAreaCfgFile)

        # Stop here is no signature is found
        if not lWorkAreaPath:
            return

        self.work.path, self.work.cfgFile = split(lWorkAreaPath)
        self.pathMaker = Pathmaker(self.srcdir, self._verbosity)

        lProjectPath = findFileInParents(kProjAreaCfgFile)

        # Stop here if no project file is found
        if not lProjectPath:
            return

        self.currentproj.path, self.currentproj.file = split(lProjectPath)
        self.currentproj.name = basename(self.currentproj.path)

        # Import project settings
        import json
        with open(lProjectPath, 'r') as lProjectFile:
            self.currentproj.config = json.load(lProjectFile)

    # ----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    def __str__(self):
        return self.__repr__() + '''({{
    working area path: {work.path}
    project area: {currentproj.name}
    configuration: {currentproj.config}
    pathMaker: {pathMaker}
    parser: {_depParser}
    }})'''.format(**(self.__dict__))
    # -----------------------------------------------------------------------------


    # -----------------------------------------------------------------------------
    @property
    def depParser(self):
        if self._depParser is None:

            self._depParser = DepFileParser(
                self.currentproj.config['toolset'],
                self.pathMaker,
                aVerbosity=self._verbosity
            )

            try:
                self._depParser.parse(
                    self.currentproj.config['topPkg'],
                    self.currentproj.config['topCmp'],
                    self.currentproj.config['topDep']
                )
            except OSError as e:
                pass

        return self._depParser
    # -----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    @property
    def srcdir(self):
        return join(self.work.path, kSourceDir) if self.work.path is not None else None
    # -----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    @property
    def projdir(self):
        return join(self.work.path, kProjDir) if self.work.path is not None else None
    # -----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    @property
    def sources(self):
        return next(walk(self.srcdir))[1]
    # -----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    @property
    def projects(self):
        return [
            lProj for lProj in next(walk(self.projdir))[1]
            if exists(join(self.projdir, lProj, kProjAreaCfgFile))
        ]
    # -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------

