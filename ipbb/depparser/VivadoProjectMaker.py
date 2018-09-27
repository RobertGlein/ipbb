from __future__ import print_function
import time
import os
import collections
import glob
import subprocess

from string import Template as tmpl


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
class VivadoProjectMaker(object):
    """
    Attributes:
        reverse        (bool): flag to invert the file import order in Vivado.
        filesets (obj:`dict`): extension-to-fileset association
    """

    filesets = {
        '.xdc': 'constrs_1',
        '.tcl': 'constrs_1',
        '.mif': 'sources_1',
        '.vhd': 'sources_1',
        '.v': 'sources_1',
        '.sv': 'sources_1',
        '.xci': 'sources_1',
        '.ngc': 'sources_1',
        '.edn': 'sources_1',
        '.edf': 'sources_1',
        '.bd': 'sources_1'
        # Legacy ISE files
        # '.ucf': 'ise_1',
        # '.xco': 'ise_1',
    }

    # --------------------------------------------------------------
    def __init__(self, aReverse = False, aTurbo=True):
        self.reverse = aReverse
        self.turbo = aTurbo
    # --------------------------------------------------------------

    # --------------------------------------------------------------
    def write(self, aTarget, aScriptVariables, aComponentPaths, aCommandList, aLibs, aMaps):
        if 'device_name' not in aScriptVariables:
            raise RuntimeError("Variable 'device_name' not defined in dep files.")

        # ----------------------------------------------------------
        # FIXME: Tempourary assignments
        write = aTarget
        lWorkingDir = os.path.abspath(os.path.join(os.getcwd(), 'top'))
        # ----------------------------------------------------------

        write('# Autogenerated project build script')
        write(time.strftime("# %c"))
        write()

        write('set outputDir {0}'.format(lWorkingDir))
        write('file mkdir $outputDir')

        write(
            'create_project top $outputDir -part {device_name}{device_package}{device_speed} -force'.format(
                **aScriptVariables
            )
        )

        # for block designs of development boards
        if 'board_part' not in aScriptVariables:
            pass
        else:
            write(
            'set_property BOARD_PART {board_part} [current_project]'.format(
                **aScriptVariables
            )
        )

        write(
            'if {[string equal [get_filesets -quiet constrs_1] ""]} {create_fileset -constrset constrs_1}')
        write(
            'if {[string equal [get_filesets -quiet sources_1] ""]} {create_fileset -srcset sources_1}')

        # Add ip repositories to the project variable
        write('set_property ip_repo_paths {{{}}} [current_project]'.format(
            ' '.join(map( lambda c: c.FilePath, aCommandList['iprepo']))
            )
        )

        write('if {[string equal [get_filesets -quiet constrs_1] ""]} {create_fileset -constrset constrs_1}')
        write('if {[string equal [get_filesets -quiet sources_1] ""]} {create_fileset -srcset sources_1}')

        for setup in aCommandList['setup']:
            write('source {0}'.format(setup.FilePath))

        lXciBasenames = []
        lXciTargetFiles = []

        lSrcs = aCommandList['src'] if not self.reverse else reversed(aCommandList['src'])

        # Grouping commands here, where the order matters only for constraint files
        lSrcCommandGroups = collections.OrderedDict()

        for src in lSrcs:
            # Extract path tokens
            lPath, lBasename = os.path.split(src.FilePath)
            lName, lExt = os.path.splitext(lBasename)
            lTargetFile = os.path.join('$outputDir/top.srcs/sources_1/ip', lName, lBasename)

            # local list of commands
            lCommands = []

            if lExt == '.xci':

                c = 'import_files -norecurse -fileset sources_1 $files'
                f = src.FilePath

                lCommands += [(c, f)]

                lXciBasenames.append(lName)
                lXciTargetFiles.append(lTargetFile)

            # Support block designs
            elif lExt == '.bd': # import pdb; pdb.set_trace()
                
                fl=glob.glob(lPath+'/*') # delete build artefacts to include recursive submodules
                fl.remove(lPath+'/'+lBasename) # do not delete the design
                if os.path.exists(lPath+'/hdl'): # do not delete hdl file if it exists
                    fl.remove(lPath+'/hdl')
                for file in fl:
                    subprocess.Popen(['rm', '-rf', file])

                # hard write to add, open, and close board design
                write(str('add_files -fileset sources_1 {'+lPath+'/'+lBasename+'}'))
                write(str('open_bd_design {'+lPath+'/'+lBasename+'}')) # open design to add all submodules
                write('close_bd_design [current_bd_design]')
                write(str('generate_target all [get_files '+lPath+'/'+lBasename+']')) # get all submodules

            else:
                if src.Include:

                    c = 'add_files -norecurse -fileset {0} $files'.format(self.filesets[lExt])
                    f = src.FilePath
                    lCommands += [(c, f)]

                    if src.Vhdl2008:
                        c = 'set_property FILE_TYPE {VHDL 2008} [get_files {$files}]'
                        f = src.FilePath
                        lCommands += [(c, f)]
                    if lExt == '.tcl':
                        c = 'set_property USED_IN implementation [get_files {$files}]'
                        f = src.FilePath
                        lCommands += [(c, f)]
                if src.Lib:
                    c = 'set_property library {0} [ get_files [ {{$files}} ] ]'.format(src.Lib)
                    f = src.FilePath
                    lCommands += [(c, f)]

            for c,f in lCommands:
                if self.turbo:
                    lSrcCommandGroups.setdefault(c, []).append(f)
                else:
                    write(tmpl(c).substitute(files=f).encode('ascii'))

        if self.turbo:
            for c,f in lSrcCommandGroups.iteritems():
                write(tmpl(c).substitute(files=' '.join(f)).encode('ascii'))

        write('set_property top top [current_fileset]')

        write('set_property "steps.synth_design.args.flatten_hierarchy" "none" [get_runs synth_1]')

        for i in lXciBasenames:
            write('upgrade_ip [get_ips {0}]'.format(i))
        for i in lXciTargetFiles:
            write('create_ip_run [get_files {0}]'.format(i))
        write('close_project')
    # --------------------------------------------------------------

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
