project(
  'dell-g-series-laptop-keyboard-controller',
  version: '0.1.0',
  meson_version: '>= 0.61.0',
  default_options: ['prefix=/usr'],
)

runtime_dir = join_paths(get_option('libexecdir'), 'dell-g-series-controller')

install_data(
  'main.py',
  'service.py',
  install_dir: runtime_dir,
  install_mode: 'rwxr-xr-x',
)

install_subdir(
  'src',
  install_dir: runtime_dir,
  exclude_directories: ['__pycache__'],
)

install_data(
  'data/alienware.svg',
  'data/dell.svg',
  install_dir: join_paths(runtime_dir, 'data'),
)

configure_file(
  input: 'data/dell-g-series-controller.in',
  output: 'dell-g-series-controller',
  configuration: {
    'launcher': join_paths(get_option('prefix'), runtime_dir, 'main.py'),
  },
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

install_data(
  'data/io.github.cemkaya_mpi.DellGSeriesController.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)

install_data(
  'data/io.github.cemkaya_mpi.DellGSeriesController.metainfo.xml',
  install_dir: join_paths(get_option('datadir'), 'metainfo'),
)

install_data(
  'data/io.github.cemkaya_mpi.DellGSeriesController.svg',
  install_dir: join_paths(
    get_option('datadir'),
    'icons',
    'hicolor',
    'scalable',
    'apps',
  ),
)

install_data(
  'data/dell-g-series-controller-brightness.service',
  install_dir: join_paths(get_option('prefix'), 'lib', 'systemd', 'user'),
)

install_data(
  'data/70-dell-g-series-controller.rules',
  install_dir: join_paths(get_option('prefix'), 'lib', 'udev', 'rules.d'),
)

test(
  'python unit tests',
  find_program('python3'),
  args: ['-m', 'unittest', 'discover', '-s', meson.current_source_dir() / 'tests'],
  env: ['PYTHONPATH=' + meson.current_source_dir()],
)
