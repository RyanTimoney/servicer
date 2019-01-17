import os
import sys
import re

from .base_package import Service as BasePackageService

class Service(BasePackageService):
    def __init__(self, config=None, logger=None):
        super().__init__(config=config, logger=logger)

        self.sbt_credentials_path = os.getenv('SBT_CREDENTIALS_PATH', '%s/.sbt/.credentials' % os.environ['HOME'])

        self.name_regex = re.compile('^\s*name\s*:=\s*[\'\"]+(.*?)[\'\"].*$', re.MULTILINE)
        self.version_regex = re.compile('^\s*version.* := [\'\"]+(\d+\.\d+\.\d+\.*\d*)(?:-SNAPSHOT)?[\'\"].*$', re.MULTILINE)
        self.scala_version_regex = re.compile('^\s*(?:val )?scala(?:Version)?\s+:?= [\'\"]+(\d+\.\d+\.\d+)[\'\"].*$', re.MULTILINE)
        self.scala_cross_version_regex = re.compile('^\s*crossScalaVersions\s+:=\s+Seq\((.*)\).*$', re.MULTILINE)
        self.package_version_format = self.config.get('package_version_format', 'version in ThisBuild := "%s"')
        self.default_version_source = 'scala_artifactory'

    def generate_sbt_credentials(self, credentials=None):
        if credentials:
            self.credentials = credentials
        else:   # setup defaults
            self.credentials = {
                'realm': os.environ['SBT_CREDENTIALS_REALM'],
                'host': os.environ['SBT_CREDENTIALS_HOST'],
                'user': os.environ['SBT_CREDENTIALS_USER'],
                'password': os.environ['SBT_CREDENTIALS_PASSWORD'],
            }

        self.logger.log('generating credentials at %s' % self.sbt_credentials_path)
        os.makedirs(os.path.dirname(self.sbt_credentials_path), exist_ok=True)
        with open(self.sbt_credentials_path, 'w') as creds:
            for key, value in self.credentials.items():
                creds.write('%s=%s\n' % (key, value))

        self.logger.log('credentials written to %s' % self.sbt_credentials_path)

    def read_package_info(self, package_info={}):
        package_file_paths = self.list_file_paths(self.config['package_directory'], '**/build.sbt')

        scala_versions = None

        if 'scala_version' in self.config['package_info']:
            scala_versions = self.config['package_info']['scala_version']

        scala_version_paths = [
            '%s/build.sbt' % self.config['package_directory'],
        ]
        for path in scala_version_paths:
            if scala_versions:
                break

            # This is where the version is determined
            scala_versions = self.scala_versions(path)

        if not scala_versions:
            raise ValueError('Scala version not defined at: %s' % scala_version_paths)

        if not isinstance(scala_versions, list):
            scala_versions = [scala_versions]

        self.package_info = []
        for package_file_path in package_file_paths:
            directory = os.path.dirname(package_file_path)

            package_version_path = '%s/version.sbt' % directory
            if os.path.exists(package_version_path):
                for sv in scala_versions:
                    pi = self.config['package_info'].copy()
                    # TODO Each version.sbt is associated with on service.
                    # It needs to be possible to define the name of the service (pi['name'])
                    # explicitly in the definition of the service, or the autoversioning will
                    # fail.
                    # UPDATE: pi['name'] is being defined in build.sbt
                    pi['name'] = self.package_name(package_file_path)
                    pi['version'] = self.package_version(package_version_path)
                    pi['version_file_path'] = package_version_path
                    self.package_info.append(pi)
                    self.results[pi['name']] = pi

    def scala_versions(self, path):
        print('scala_versions is running with path: %s' % path)
        with open(path) as f:
            text = f.read()

            print('about to run scala_cross_version_regex.search')
            cross_version_result = self.scala_cross_version_regex.search(text)
            if cross_version_result:
                return ''.join(cross_version_result.groups()[0].split()).replace('"', '').split(',')

            print('about to get_existing_versions')
            result = self.get_existing_versions(self.config['package_info'])
            if result:
                return result.groups()[0]