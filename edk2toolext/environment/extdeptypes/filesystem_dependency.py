# @file web_dependency.py
# This module implements ExternalDependency for files that are available for download online.
#
##
# Copyright (c) Microsoft Corporation
#
# SPDX-License-Identifier: BSD-2-Clause-Patent
##

import os
import logging
import shutil
import tarfile
import zipfile
import tempfile
import urllib.error
import urllib.request
from edk2toolext.environment.external_dependency import ExternalDependency


class FsDependency(ExternalDependency):
    '''
    ext_dep fields:
    - internal_path: Describes layout of what we're downloading. Include / at the beginning
                     if the ext_dep is a directory. Item located at internal_path will
                     unpacked into the ext_dep folder and this is what the path/shell vars
                     will point to when compute_published_path is run.
    - compression_type: optional. supports zip and tar. If the file isn't compressed, do not include this field.
    - sha256: optional. hash of downloaded file to be checked against.
    '''

    TypeString = "Fs"

    def __init__(self, descriptor):
        super().__init__(descriptor)
        self.source = os.path.normpath(descriptor['source'])
        self.dest = os.path.normpath(descriptor.get('dest', ''))
        self.compression_type = descriptor.get('compression_type', None)

    def __str__(self):
        """ return a string representation of this """
        return f"FsDependecy: {self.source}"

    def linuxize_path(path):
        '''
        path: path that uses os.sep, to be replaced with / for compatibility with zipfile
        '''
        return "/".join(path.split("\\"))

    def unpack(compressed_file_path, destination, internal_path, compression_type):
        '''
        compressed_file_path: name of compressed file to unpack.
        destination: directory you would like it unpacked into.
        internal_path: internal structure of the compressed volume that you would like extracted.
        compression_type: type of compression. tar and zip supported.
        '''

        # First, we will open the file depending on the type of compression we're dealing with.

        # tarfile and zipfile both use the Linux path seperator / instead of using os.sep
        linux_internal_path = WebDependency.linuxize_path(internal_path)

        if compression_type == "zip":
            logging.info(f"{compressed_file_path} is a zip file, trying to unpack it.")
            _ref = zipfile.ZipFile(compressed_file_path, 'r')
            files_in_volume = _ref.namelist()

        elif compression_type and "tar" in compression_type:
            logging.info(f"{compressed_file_path} is a tar file, trying to unpack it.")
            # r:* tells tarfile to look at the header and figure out how to extract it
            _ref = tarfile.open(compressed_file_path, "r:*")
            files_in_volume = _ref.getnames()

        else:
            raise RuntimeError(f"{compressed_file_path} was labeled as {compression_type}, which is not supported.")

        # Filter the files inside to only the ones that are inside the important folder
        files_to_extract = [name for name in files_in_volume if linux_internal_path in name]

        for file in files_to_extract:
            _ref.extract(member=file, path=destination)
        _ref.close()
    def verify(self):
        return False
    def fetch(self):
        try:
            if self.compression_type:
                FsDependency.unpack(temp_file_path, temp_folder, self.internal_path, self.compression_type)
            print(self.source, os.path.join(self.contents_dir, self.dest))
            if os.path.isdir(self.source):
                shutil.copytree(self.source, self.contents_dir)
            else:
                if not os.path.exists(self.contents_dir):
                    os.makedirs(self.contents_dir)
                shutil.copy2(self.source, os.path.join(self.contents_dir, self.dest))
                self.published_path = os.path.join(self.contents_dir, self.dest)
        except urllib.error.HTTPError as e:
            logging.error(f"ran into an issue when resolving ext_dep {self.name} at {self.source}")
            raise e
