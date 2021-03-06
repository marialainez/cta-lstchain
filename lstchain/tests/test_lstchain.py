from ctapipe.utils import get_dataset_path
import numpy as np
import pytest
import os
import pandas as pd
from lstchain.io.io import dl1_params_lstcam_key, dl2_params_lstcam_key, dl1_images_lstcam_key
from lstchain.io import standard_config
from lstchain.reco.utils import filter_events
import astropy.units as u
import tables
from pathlib import Path

test_dir = 'testfiles'

os.makedirs(test_dir, exist_ok=True)

mc_gamma_testfile = get_dataset_path('gamma_test_large.simtel.gz')
dl1_file = os.path.join(test_dir, 'dl1_gamma_test_large.h5')
dl2_file = os.path.join(test_dir, 'dl2_gamma_test_large.h5')
fake_dl2_proton_file = os.path.join(test_dir, 'dl2_fake_proton.simtel.h5')
fake_dl1_proton_file = os.path.join(test_dir, 'dl1_fake_proton.simtel.h5')
file_model_energy = os.path.join(test_dir, 'reg_energy.sav')
file_model_disp = os.path.join(test_dir, 'reg_disp_vector.sav')
file_model_gh_sep = os.path.join(test_dir, 'cls_gh.sav')
r0_file = Path('test_data/real/R0/20200218/LST-1.1.Run02008.0000_first50.fits.fz')


def test_import_calib():
    from lstchain import calib

def test_import_reco():
    from lstchain import reco

def test_import_visualization():
    from lstchain import visualization

def test_import_lstio():
    from lstchain import io

@pytest.mark.run(order=1)
def test_r0_to_dl1():
    from lstchain.reco.r0_to_dl1 import r0_to_dl1
    infile = mc_gamma_testfile
    r0_to_dl1(infile, custom_config=standard_config, output_filename=dl1_file)


@pytest.mark.private_data
def test_r0_available():
    assert r0_file.is_file()

@pytest.mark.run(after='test_r0_to_dl1')
def test_content_dl1():
    # test presence of images and parameters
    with tables.open_file(dl1_file) as f:
        images_table = f.root[dl1_images_lstcam_key]
        params_table = f.root[dl1_params_lstcam_key]
        assert 'image' in images_table.colnames
        assert 'peak_time' in images_table.colnames
        assert 'tel_id' in images_table.colnames
        assert 'obs_id' in images_table.colnames
        assert 'event_id' in images_table.colnames
        assert 'tel_id' in params_table.colnames
        assert 'event_id' in params_table.colnames
        assert 'obs_id' in params_table.colnames

def test_get_source_dependent_parameters():
    from lstchain.reco.dl1_to_dl2 import get_source_dependent_parameters

    dl1_params = pd.read_hdf(dl1_file, key=dl1_params_lstcam_key)
    src_dep_df = get_source_dependent_parameters(dl1_params, standard_config)

@pytest.mark.run(order=2)
def test_build_models():
    from lstchain.reco.dl1_to_dl2 import build_models
    infile = dl1_file

    reg_energy, reg_disp, cls_gh = build_models(infile, infile, custom_config=standard_config, save_models=False)

    import joblib
    joblib.dump(reg_energy, file_model_energy)
    joblib.dump(reg_disp, file_model_disp)
    joblib.dump(cls_gh, file_model_gh_sep)


@pytest.mark.run(order=3)
def test_apply_models():
    from lstchain.reco.dl1_to_dl2 import apply_models
    import joblib

    dl1 = pd.read_hdf(dl1_file, key=dl1_params_lstcam_key)
    dl1 = filter_events(dl1,
                        filters=standard_config["events_filters"],
                        finite_params=standard_config['regression_features'] + standard_config['classification_features'],
                        )

    reg_energy = joblib.load(file_model_energy)
    reg_disp = joblib.load(file_model_disp)
    reg_cls_gh = joblib.load(file_model_gh_sep)


    dl2 = apply_models(dl1, reg_cls_gh, reg_energy, reg_disp, custom_config=standard_config)
    dl2.to_hdf(dl2_file, key=dl2_params_lstcam_key)

def produce_fake_dl1_proton_file(dl1_file):
    """
    Produce a fake dl1 proton file by copying the dl2 gamma test file
    and changing mc_type
    """
    events = pd.read_hdf(dl1_file, key=dl1_params_lstcam_key)
    events.mc_type = 101
    events.to_hdf(fake_dl1_proton_file, key=dl1_params_lstcam_key)

def produce_fake_dl2_proton_file(dl2_file):
    """
    Produce a fake dl2 proton file by copying the dl2 gamma test file
    and changing mc_type
    """
    events = pd.read_hdf(dl2_file, key=dl2_params_lstcam_key)
    events.mc_type = 101
    events.to_hdf(fake_dl2_proton_file, key=dl2_params_lstcam_key)

@pytest.mark.run(after='produce_fake_dl2_proton_file')
def test_sensitivity():
    from lstchain.mc.sensitivity import find_best_cuts_sensitivity, sensitivity

    produce_fake_dl2_proton_file(dl2_file)

    nfiles_gammas = 1
    nfiles_protons = 1

    eb = 10  # Number of energy bins
    gb = 11  # Number of gammaness bins
    tb = 10  # Number of theta2 bins
    obstime = 50 * 3600 * u.s
    noff = 2


    E, best_sens, result, units, gcut, tcut = find_best_cuts_sensitivity(dl1_file,
                                                                         dl1_file,
                                                                         dl2_file,
                                                                         fake_dl2_proton_file,
                                                                         1, 1,
                                                                         eb, gb, tb, noff,
                                                                         obstime)

    E, best_sens, result, units, dl2 = sensitivity(dl1_file,
                                                   dl1_file,
                                                   dl2_file,
                                                   fake_dl2_proton_file,
                                                   1, 1,
                                                   eb, gcut, tcut * (u.deg ** 2), noff,
                                                   obstime)


@pytest.mark.last
def test_clean_test_files():
    """
    Function to clean the test files created by the previous test
    """
    import shutil
    shutil.rmtree(test_dir)


def test_disp_vector():
    from lstchain.reco.disp import disp_vector
    dx = np.cos(np.pi/3 * np.ones(3))
    dy = np.sin(np.pi/3 * np.ones(3))
    disp_angle = np.pi/3 * np.ones(3)
    disp_norm = np.ones(3)
    disp_sign = np.ones(3)
    disp_dx, disp_dy = disp_vector(disp_norm, disp_angle, disp_sign)
    np.testing.assert_array_equal([dx, dy], [disp_dx, disp_dy])


def test_disp_to_pos():
    from lstchain.reco.disp import disp_to_pos
    x = np.random.rand(3)
    y = np.random.rand(3)
    cog_x = np.random.rand(3)
    cog_y = np.random.rand(3)
    X, Y = disp_to_pos(x, y, cog_x, cog_y)
    np.testing.assert_array_equal([X, Y], [x+cog_x, y+cog_y])


def test_change_frame_camera_sky():
    from lstchain.reco.utils import sky_to_camera, camera_to_altaz
    import astropy.units as u
    x = np.random.rand(1) * u.m
    y = np.random.rand(1) * u.m
    focal_length = 5 * u.m
    pointing_alt = np.pi/3. * u.rad
    pointing_az = 0. * u.rad

    sky_pos = camera_to_altaz(x, y, focal_length, pointing_alt, pointing_az)
    cam_pos = sky_to_camera(sky_pos.alt, sky_pos.az, focal_length, pointing_alt, pointing_az)
    np.testing.assert_almost_equal([x, y], [cam_pos.x, cam_pos.y], decimal=4)


def test_polar_cartesian():
    from lstchain.reco.utils import polar_to_cartesian, cartesian_to_polar
    X = [-0.5, 0.5]
    Y = [-0.5, 0.5]
    for x in X:
        for y in Y:
            p = cartesian_to_polar(x, y)
            np.testing.assert_almost_equal((x, y), polar_to_cartesian(*p))


def test_version_not_unkown():
    """
    Test that lstchain.__version__ is not unkown
    """
    import lstchain
    assert lstchain.__version__ != 'unknown'
