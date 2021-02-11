import os
import shutil
import subprocess as sp

import numpy as np
import pandas as pd
import pkg_resources
import pytest

from lstchain.io.io import dl1_params_lstcam_key
from lstchain.io.io import dl1_params_src_dep_lstcam_key
from lstchain.tests.test_lstchain import test_dir, mc_gamma_testfile, produce_fake_dl1_proton_file, fake_dl1_proton_file
from pathlib import Path

output_dir = os.path.join(test_dir, 'scripts')
dl1_file = os.path.join(output_dir, 'dl1_gamma_test_large.h5')
merged_dl1_file = os.path.join(output_dir, 'script_merged_dl1.h5')
dl2_file = os.path.join(output_dir, 'dl2_gamma_test_large.h5')
file_model_energy = os.path.join(output_dir, 'reg_energy.sav')
file_model_disp = os.path.join(output_dir, 'reg_disp_vector.sav')
file_model_gh_sep = os.path.join(output_dir, 'cls_gh.sav')
r0_file = Path('test_data/real/R0/20200218/LST-1.1.Run02008.0000_first50.fits.fz')
real_data_dl1_path = Path('test_data/real/DL1/20200218')
real_data_dl1_file = real_data_dl1_path / 'dl1_LST-1.Run02008.0000.h5'
real_data_dl2_path = Path('test_data/real/DL2/20200218')
real_data_dl2_file = real_data_dl2_path / 'dl2_LST-1.Run02008.0000.h5'
drs4_pedestal_file = Path('test_data/real/calibration/20200218/v05/drs4_pedestal.Run2005.0000.fits')
calibration_file = Path('test_data/real/calibration/20200218/v05/calibration.Run2006.0000.hdf5')
time_calibration_file = Path('test_data/real/calibration/20200218/v05/time_calibration.Run2006.0000.hdf5')
drive_file = Path('test_data/real/monitoring/DrivePositioning/drive_log_20200218.txt')
muons_file = real_data_dl1_path / 'muons_LST-1.Run02008.0000.fits'
datacheck_file = real_data_dl1_path / 'datacheck_dl1_LST-1.Run02008.0000.h5'

os.makedirs(real_data_dl1_path, exist_ok=True)
os.makedirs(real_data_dl2_path, exist_ok=True)


def find_entry_points(package_name):
    '''from: https://stackoverflow.com/a/47383763/3838691'''
    entrypoints = [
        ep.name
        for ep in pkg_resources.iter_entry_points('console_scripts')
        if ep.module_name.startswith(package_name)
    ]
    return entrypoints


ALL_SCRIPTS = find_entry_points('lstchain')


def run_program(*args):
    result = sp.run(
        args,
        stdout=sp.PIPE, stderr=sp.STDOUT, encoding='utf-8'
    )

    if result.returncode != 0:
        raise ValueError(
            f'Running {args[0]} failed with return code {result.returncode}'
            f', output: \n {result.stdout}'
        )


@pytest.mark.parametrize('script', ALL_SCRIPTS)
def test_all_help(script):
    '''Test for all scripts if at least the help works'''
    run_program(script, '--help')


def test_lstchain_mc_r0_to_dl1():
    input_file = mc_gamma_testfile
    run_program(
        'lstchain_mc_r0_to_dl1',
        '-f', input_file,
        '-o', output_dir
    )
    assert os.path.exists(dl1_file)


def test_lstchain_data_r0_to_dl1():
    r0_file_renamed = Path('test_data/real/R0/20200218/LST-1.1.Run02008.0000.fits.fz')
    shutil.copy(r0_file, r0_file_renamed)
    if real_data_dl1_path.exists() and real_data_dl1_path.is_dir():
        shutil.rmtree(real_data_dl1_path)
    run_program(
        'lstchain_data_r0_to_dl1',
        '-f', r0_file_renamed,
        '-o', real_data_dl1_path,
        '--pedestal-file', drs4_pedestal_file,
        '--calibration-file', calibration_file,
        '--time-calibration-file', time_calibration_file,
        '--pointing-file', drive_file,
        '--ucts-t0-dragon', '1582059789516351903',
        '--dragon-counter0', '2516351600',
        '--ucts-t0-tib', '1582059789516351903',
        '--tib-counter0', '2516351200'
    )
    assert real_data_dl1_file.is_file()
    assert muons_file.is_file()
    assert datacheck_file.is_file()


@pytest.mark.run(after='test_lstchain_mc_r0_to_dl1')
def test_add_source_dependent_parameters():
    run_program('lstchain_add_source_dependent_parameters', '-f', dl1_file)
    dl1_params_src_dep = pd.read_hdf(dl1_file, key=dl1_params_src_dep_lstcam_key)
    assert 'alpha' in dl1_params_src_dep.columns


@pytest.mark.run(after='test_lstchain_mc_r0_to_dl1')
def test_lstchain_mc_trainpipe():
    gamma_file = dl1_file
    proton_file = dl1_file

    run_program(
        'lstchain_mc_trainpipe',
        '--fg', gamma_file,
        '--fp', proton_file,
        '-o', output_dir
    )

    assert os.path.exists(file_model_gh_sep)
    assert os.path.exists(file_model_disp)
    assert os.path.exists(file_model_energy)


@pytest.mark.run(after='test_lstchain_mc_r0_to_dl1')
def test_lstchain_mc_rfperformance():
    gamma_file = dl1_file
    produce_fake_dl1_proton_file(dl1_file)
    proton_file = fake_dl1_proton_file

    run_program(
        'lstchain_mc_rfperformance',
        '--g-train', gamma_file,
        '--g-test', gamma_file,
        '--p-train', proton_file,
        '--p-test', proton_file,
        '-o', output_dir
    )

    assert os.path.exists(file_model_gh_sep)
    assert os.path.exists(file_model_disp)
    assert os.path.exists(file_model_energy)


@pytest.mark.run(after='test_lstchain_mc_r0_to_dl1')
def test_lstchain_merge_dl1_hdf5_files():
    shutil.copy(dl1_file, os.path.join(output_dir, 'dl1_copy.h5'))
    run_program('lstchain_merge_hdf5_files',
                '-d', output_dir,
                '-o', merged_dl1_file,
                '--no-image', 'True',
                )
    assert os.path.exists(merged_dl1_file)


@pytest.mark.run(after='test_lstchain_merge_dl1_hdf5_files')
def test_lstchain_merged_dl1_to_dl2():
    output_file = merged_dl1_file.replace('dl1', 'dl2')
    run_program(
        'lstchain_dl1_to_dl2',
        '-f', merged_dl1_file,
        '-p', output_dir,
        '-o', output_dir,
    )
    assert os.path.exists(output_file)


@pytest.mark.run(after='test_lstchain_trainpipe')
def test_lstchain_dl1_to_dl2():
    run_program(
        'lstchain_dl1_to_dl2',
        '-f', dl1_file,
        '-p', output_dir,
        '-o', output_dir,
    )
    assert os.path.exists(dl2_file)


@pytest.mark.run(after='test_lstchain_data_r0_to_dl1')
def test_lstchain_realdata_dl1_to_dl2():
    if real_data_dl2_path.exists() and real_data_dl2_path.is_dir():
        shutil.rmtree(real_data_dl2_path)
    run_program(
        'lstchain_dl1_to_dl2',
        '--input-file', real_data_dl1_file,
        '--path-models', output_dir,
        '--output-dir', real_data_dl2_path,
    )
    assert os.path.exists(real_data_dl2_file)


@pytest.mark.run(after='test_lstchain_mc_r0_to_dl1')
def test_dl1ab():
    output_file = os.path.join(output_dir, 'dl1ab.h5')
    run_program('lstchain_dl1ab',
                '-f', dl1_file, 
                '-o', output_file,
                )
    assert os.path.exists(output_file)


@pytest.mark.run(after='test_lstchain_data_r0_to_dl1')
def test_dl1ab_realdata():
    output_real_data_dl1ab = real_data_dl1_path / 'dl1ab.h5'
    run_program('lstchain_dl1ab',
                '-f', real_data_dl1_file,
                '-o', output_real_data_dl1ab
                )
    assert os.path.exists(output_real_data_dl1ab)


@pytest.mark.run(after='test_dl1ab')
def test_dl1ab_validity():
    dl1 = pd.read_hdf(os.path.join(output_dir, 'dl1_gamma_test_large.h5'), key=dl1_params_lstcam_key)
    dl1ab = pd.read_hdf(os.path.join(output_dir, 'dl1ab.h5'), key=dl1_params_lstcam_key)
    np.testing.assert_allclose(dl1, dl1ab, rtol=1e-4, equal_nan=True)


@pytest.mark.run(after='test_dl1ab_realdata')
def test_dl1ab_realdata_validity():
    output_real_data_dl1ab = real_data_dl1_path / 'dl1ab.h5'
    dl1 = pd.read_hdf(real_data_dl1_file, key=dl1_params_lstcam_key)
    dl1ab = pd.read_hdf(output_real_data_dl1ab, key=dl1_params_lstcam_key)
    np.testing.assert_allclose(dl1, dl1ab, rtol=1e-4, equal_nan=True)


@pytest.mark.run(after='test_lstchain_dl1_to_dl2')
def test_mc_r0_to_dl2():
    os.remove(dl1_file)
    os.remove(dl2_file)

    run_program(
        'lstchain_mc_r0_to_dl2',
        '-f', mc_gamma_testfile,
        '-p', output_dir,
        '-s1', 'False',
        '-o', output_dir,
    )
    assert os.path.exists(dl2_file)


@pytest.mark.run(after='test_mc_r0_to_dl2')
def test_read_dl2_to_pyirf():
    from lstchain.io.io import read_dl2_to_pyirf
    import astropy.units as u
    events, sim_info = read_dl2_to_pyirf(dl2_file)
    assert 'true_energy' in events.colnames
    assert sim_info.energy_max == 330 * u.TeV
