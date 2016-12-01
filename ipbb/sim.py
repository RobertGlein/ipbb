from __future__ import print_function
#------------------------------------------------------------------------------

# Modules
import click
import os
import ipbb
import subprocess

# Elements
from os.path import join, split, exists, splitext, basename, dirname, abspath
from tools.common import which, do, makeParser, ensuresudo
from .common import DirSentry


#------------------------------------------------
class ModelsimNotFoundError(Exception):

  def __init__(self, message):
    # Call the base class constructor with the parameters it needs
    super(ModelsimNotFoundError, self).__init__(message)
#------------------------------------------------


#------------------------------------------------------------------------------
@click.group() # chain = True
def sim():
  pass    
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# FIXME: duplicated in vivado.create
def _validateComponent(ctx, param, value):
  lSeparators = value.count(':')
  # Validate the format
  if lSeparators > 1:
    raise click.BadParameter('Malformed component name : %s. Expected <module>:<component>' % value)
  
  return tuple(value.split(':'))


@sim.command()
@click.argument('workarea')
@click.argument('component', callback=_validateComponent)
@click.option('-t', '--topdep', default='top.dep', help='Top-level dependency file')
@click.pass_obj
def create( env, workarea, component, topdep ):
  '''Create a new ModelSim/QuestaSim working area'''
  #------------------------------------------------------------------------------
  # Must be in a build area
  if env.root is None:
    raise click.ClickException('Build area root directory not found')
  #------------------------------------------------------------------------------

  #------------------------------------------------------------------------------
  lWorkAreaPath = join(env.root, workarea)
  if exists(lWorkAreaPath):
    raise click.ClickException('Directory %s already exists' % lWorkAreaPath)
  #------------------------------------------------------------------------------

  #------------------------------------------------------------------------------
  from dep2g.Pathmaker import Pathmaker
  lPathmaker = Pathmaker(env.src, 0)
  lTopPackage, lTopComponent = component
  lTopDepPath = lPathmaker.getPath(lTopPackage, lTopComponent, 'include', topdep)
  if not exists(lTopDepPath):
    raise click.ClickException('Top-level dependency file %s not found' % lTopDepPath)
  #------------------------------------------------------------------------------

  # Build source code directory
  os.makedirs(lWorkAreaPath)

  lCfg = {
    'product': 'sim',
    'topPkg': lTopPackage,
    'topCmp': lTopComponent,
    'topDep': topdep,
  }
  with open(join(lWorkAreaPath,ipbb.kWorkFileName),'w') as lWorkFile:
    import json
    json.dump(lCfg, lWorkFile, indent=2)

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
@sim.command()
@click.option('-o', '--output', default=None)
@click.pass_obj
def ipcores(env, output):

  #------------------------------------------------------------------------------
  # Must be in a build area
  if env.work is None:
    raise click.ClickException('Work area root directory not found')
  
  if env.workConfig['product'] != 'sim':
    raise click.ClickException("Work area product mismatch. Expected 'sim', found '%s'" % env.workConfig['product'] )
  #------------------------------------------------------------------------------

  #------------------------------------------------------------------------------
  if not which('vivado'):
  # if 'XILINX_VIVADO' not in os.environ:
    raise click.ClickException('Vivado is not available. Have you sourced the environment script?' )
  #------------------------------------------------------------------------------

  lDepFileParser, lPathmaker, lCommandLineArgs = makeParser( env, 3 )

  from dep2g.IPCoresSimMaker import IPCoresSimMaker
  lWriter = IPCoresSimMaker(lCommandLineArgs, lPathmaker)

  # FIXME: Yeah, this is a hack
  os.environ['XILINX_SIMLIBS'] = join('.xil_sim_libs',basename(os.environ['XILINX_VIVADO']))

  if output:
    from dep_tree.SmartOpen import SmartOpen
    with SmartOpen(output) as lTarget:
      lWriter.write(lTarget,lDepFileParser.ScriptVariables, lDepFileParser.Components, lDepFileParser.CommandList , lDepFileParser.Libs, lDepFileParser.Maps)
  else:
    import tools.xilinx
    with tools.xilinx.VivadoOpen() as lTarget:
      lWriter.write(lTarget,lDepFileParser.ScriptVariables, lDepFileParser.Components, lDepFileParser.CommandList , lDepFileParser.Libs, lDepFileParser.Maps)
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
@sim.command()
@click.pass_obj
def fli(env):

  #------------------------------------------------------------------------------
  # Must be in a build area
  if env.work is None:
    raise click.ClickException('Work area root directory not found')
  
  if env.workConfig['product'] != 'sim':
    raise click.ClickException("Work area product mismatch. Expected 'sim', found '%s'" % env.workConfig['product'] )
  #------------------------------------------------------------------------------

  # Set ModelSim root based on vsim's path
  os.environ['MODELSIM_ROOT'] = ( dirname( dirname( which( 'vsim' ) ) ) )

  lFliSrc = join(env.src, 'ipbus-fw-dev', 'components', 'ipbus_eth', 'firmware', 'sim', 'modelsim_fli')
  lCmds = '''  
rm -rf modelsim_fli
cp -a {0} ./
cd modelsim_fli && ./mac_fli_compile.sh
cp modelsim_fli/mac_fli.so .
'''.format(lFliSrc)

  do( lCmds )
#------------------------------------------------------------------------------


#------------------------------------------------------------------------------
@sim.command()
@click.option('-o', '--output', default=None)
@click.pass_obj
def project( env, output ):

  #------------------------------------------------------------------------------
  # Must be in a build area
  if env.work is None:
    raise click.ClickException('Work area root directory not found')
  
  if env.workConfig['product'] != 'sim':
    raise click.ClickException("Work area product mismatch. Expected 'sim', found '%s'" % env.workConfig['product'] )
  #------------------------------------------------------------------------------

  #------------------------------------------------------------------------------
  if not which('vsim'):
    raise click.ClickException('ModelSim is not available. Have you sourced the environment script?' )
  #------------------------------------------------------------------------------

  lDepFileParser, lPathmaker, lCommandLineArgs = makeParser( env, 3 )

  from dep2g.ModelSimProjectMaker import ModelSimProjectMaker
  lWriter = ModelSimProjectMaker(lCommandLineArgs, lPathmaker)

  if output:
    if output == 'stdout': output = None
    from dep_tree.SmartOpen import SmartOpen
    with SmartOpen(output) as lTarget:
      lWriter.write(lTarget,lDepFileParser.ScriptVariables, lDepFileParser.Components, lDepFileParser.CommandList , lDepFileParser.Libs, lDepFileParser.Maps)
  else:
    import tools.mentor
    with tools.mentor.ModelSimOpen() as lTarget:
      lWriter.write(lTarget,lDepFileParser.ScriptVariables, lDepFileParser.Components, lDepFileParser.CommandList , lDepFileParser.Libs, lDepFileParser.Maps)


  #----------------------------------------------------------
  # FIXME: Tempourary assignments
  lWorkingDir = abspath( join( os.getcwd() , 'top' ) )
  #----------------------------------------------------------

  #----------------------------------------------------------
  # Collect the list of libraries generated by ipcores to add them to modelsim.ini
  lSimLibDirectory = abspath( join( lWorkingDir, 'top.sim','sim_1','behav','msim') )
  lSimLibs = next(os.walk(lSimLibDirectory))[1]
  print ( 'Detected simulation libraries: ', ', '.join( lSimLibs ) )


  # add newly generated libraries to modelsim.ini
  print ( 'Adding generated simulation libraries to modelsim.ini' )
  import ConfigParser
  
  lModelsimIni = ConfigParser.RawConfigParser()
  lModelsimIni.read('modelsim.ini')
  print(lModelsimIni.sections())
  for lSimLib in lSimLibs:
    lModelsimIni.set('Library',lSimLib,join(lSimLibDirectory,lSimLib))

  # Make a backup copy of modelsim.ini (generated by ipcores)
  os.rename('modelsim.ini','modelsim.ini.bak')
  with SmartOpen( 'modelsim.ini' ) as newIni:
    lModelsimIni.write(newIni.file)
  
  #----------------------------------------------------------
  # Create a wrapper to force default bindings at load time
  print ( 'Writing modelsim wrapper \'./vsim\'' )
  with SmartOpen('vsim') as lVsimSh:
    lVsimSh ( '#!/bin/sh' )
    lVsimSh ( 'vsim ' + ' '.join('-L '+l for l in lSimLibs ) + ' $@')

  # Make it executable
  os.chmod('vsim', 0755)


#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
@sim.command()
@click.argument('name', default='tap0')
@click.option('--ip', default='192.168.201.1')
@click.pass_obj
def virtualtap(env, name, ip):

  ensuresudo()

  lCmds = '''
sudo openvpn --mktun --dev {0}
sudo /sbin/ifconfig {0} up {1}
sudo chmod a+rw /dev/net/tun
'''.format(name, ip)
  
  do( lCmds )
#------------------------------------------------------------------------------