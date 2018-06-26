#!/usr/bin/env python
# -*- coding: utf8 -*-

import ccdproc
import glob
import numpy
import os

from soar_sami.io import pyfits
from soar_sami.io.logging import get_logger, MyLogFormatter
from soar_sami.data_reduction import merge, combine

astropy_logger = get_logger('astropy')
astropy_logger.setLevel('NOTSET')

ccdproc_logger = get_logger('ccdproc')
ccdproc_logger.setLevel('NOTSET')

log = get_logger('samidr')
log.propagate = False

__author__ = 'Bruno Quint'

KEYWORDS = ["OBSTYPE", "FILTERS", "CCDSUM"]


def reduce_sami(path):
    
    sami_merger = merge.SamiMerger()

    log.info('Creating directory for reduced data: {}'.format(
        os.path.join(path, 'RED')))

    os.makedirs(os.path.join(path, "RED"), exist_ok=True)
    list_of_files = glob.glob(os.path.join(path, '*.fits'))


    log.info('Reading raw files')
    table = []
    for _file in list_of_files:

        try:
            hdu = pyfits.open(_file)
        except OSError:
            log.warning("Could not read file: {}".format(_file))
            continue

        if numpy.std(hdu[1].data.ravel()) == 0:
            log.warning("Bad data found on file: {}".format(_file))
            continue

        row = {
            'filename': _file,
            'obstype': hdu[0].header['obstype'],
            'filter_id': hdu[0].header['filters'],
            'filter_name': hdu[0].header['filters'],
            'binning': [
                int(b) for b in hdu[1].header['ccdsum'].strip().split(' ')]
        }

        table.append(row)

    list_of_binning = []
    for row in table:
        if row['binning'] not in list_of_binning:
            list_of_binning.append(row['binning'])
            log.info('Found new binning mode: {}'.format(
                row['binning'][0], row['binning'][1]))

    for binning in list_of_binning:

        log.info('Organizing data.')
        sub_table = [row for row in table if row['binning'] == binning]

        zero_table = [row for row in sub_table if row['obstype'] == 'ZERO']
        dflat_table = [row for row in sub_table if row['obstype'] == 'DFLAT']
        sflat_table = [row for row in sub_table if row['obstype'] == 'SFLAT']
        obj_table = [row for row in sub_table if row['obstype'] == 'OBJECT']

        log.info('Processing ZERO files')
        zero_files = [r['filename'] for r in zero_table]
        zero_files.sort()

        zero_list_name = os.path.join(
            path, "RED", "0Zero{}x{}".format(binning[0], binning[1]))

        with open(zero_list_name, 'w') as zero_list_buffer:

            for zero_file in zero_files:

                log.info('Processing ZERO file: {}'.format(zero_file))
                data = sami_merger.get_joined_data(zero_file)
                header = pyfits.getheader(zero_file)

                data, header, prefix = sami_merger.join_and_process(data, header)

                path, fname = os.path.split(zero_file)
                zero_file = os.path.join(path, 'RED', prefix + fname)
                pyfits.writeto(zero_file, data, header)

                zero_list_buffer.write('{:s}\n'.format(zero_file))

        log.info('Combining ZERO files.')

        ic = ccdproc.ImageFileCollection(location=os.path.join(path, 'RED'),
                                         glob_include='*.fits',
                                         keywords=KEYWORDS)

        zero_combine_files = [
            os.path.join(path, 'RED', f)
            for f in ic.files_filtered(obstype='ZERO')]

        master_zero_fname = zero_list_name + '.fits'
        log.info("Writing master zero to: {}".format(master_zero_fname))

        zero_combine = combine.ZeroCombine(
            input_list=zero_combine_files,
            output_file=master_zero_fname
        )

        zero_combine.run()

        log.info('Done.')

        log.info('Processing FLAT files (SFLAT + DFLAT)')
        flat_table = sflat_table + dflat_table
        filters_used = []
        for row in flat_table:
            if row['filter_id'] not in filters_used:
                filters_used.append(row['filter_id'])
                log.info('Found new filter: {}'.format(row['filter_name']))

        for _filter in filters_used:

            log.info('Processing FLATs for filter: {}'.format(_filter))

            sub_table_by_filter = [
                row for row in flat_table if row['filter_id'] == _filter
            ]

            flat_list_name = os.path.join(
                path, 'RED',
                "1FLAT_{}x{}_{}".format(binning[0], binning[1], _filter)
            )

            flat_files = [row['filename'] for row in sub_table_by_filter]
            flat_files.sort()

            flat_combine_files = []

            with open(flat_list_name, 'w') as flat_list_buffer:

                for flat_file in flat_files:

                    log.info('Processing FLAT file: {}'.format(flat_file))
                    sami_merger.flat_file = None
                    sami_merger.zero_file = master_zero_fname


                    d = sami_merger.get_joined_data(flat_file)
                    h = pyfits.getheader(flat_file)

                    d, h, p = sami_merger.join_and_process(d, h)

                    path, fname = os.path.split(flat_file)
                    flat_file = os.path.join(path, 'RED', p + fname)
                    pyfits.writeto(flat_file, d, h)

                    flat_list_buffer.write('{:s}\n'.format(flat_file))

                    flat_combine_files.append(flat_file)

            master_flat_fname = flat_list_name + '.fits'
            log.info('Writing master FLAT to file: {}'.format(
                master_flat_fname))

            flat_combine = combine.FlatCombine(
                 input_list=flat_combine_files,
                 output_file=master_flat_fname
            )

            flat_combine.run()

            sub_table_by_filter = [
                row for row in obj_table if row['filter_id'] == _filter
            ]

            log.info('Processing OBJECT files with filter: {}'.format(
                _filter))

            obj_list_name = os.path.join(
                path, 'RED',
                "2OBJECT_{}x{}_{}".format(binning[0], binning[1], _filter)
            )

            obj_files = [row['filename'] for row in sub_table_by_filter]
            obj_files.sort()

            with open(obj_list_name, 'w') as obj_list_buffer:

                for obj_file in obj_files:

                    log.info('Processing OBJECT file: {}'.format(obj_file))
                    sami_merger.zero_file = master_zero_fname
                    sami_merger.flat_file = master_flat_fname
                    sami_merger.cosmic_rays = True

                    d = sami_merger.get_joined_data(obj_file)
                    h = pyfits.getheader(obj_file)

                    d, h, p = sami_merger.join_and_process(d, h)

                    path, fname = os.path.split(obj_file)
                    obj_file = os.path.join(path, 'RED', p + fname)
                    pyfits.writeto(obj_file, d, h)

                    obj_list_buffer.write('\n'.format(obj_file))

            log.info('All done.')

