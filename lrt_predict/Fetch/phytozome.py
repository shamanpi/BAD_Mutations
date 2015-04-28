#!/usr/bin/env python
"""Defines a class that is used to fetch data from Phytozome 10."""

#   Import python modules here
import requests
from xml.etree import ElementTree
import os

#   Import our helper scripts here
from lrt_predict.General import dir_funcs
from lrt_predict.General import file_funcs
from lrt_predict.Fetch import format_blast
from lrt_predict.Fetch import phytozome_species
from lrt_predict.General import set_verbosity
from lrt_predict.General import check_modules


#   A new class to handle the requests to and responses from JGI
class Phytozome(object):
    """A class to handle fetching data from Phytozome 10, hosted by the Joint
    Genome Institute of the US Department of Energy.
    URL: http://phytozome.jgi.doe.gov

    Contains the following class attributes:
        JGI_LOGIN (str)       Sign in URL for JGI Genome Portal
        DL_BASE (str)         URL to the root of the downloads directory
        XML_URL (str)         URL to the XML file describing the downloads tree
        XML_DATA (dict)       HTTP GET variables used to request every species
                              for download
        FAILED_LOGIN (str)    Text to search for for identifying if a login
                              attempt has failed
        EXPIRED_ACCOUNT (str) Text to search for for identifying if an account
                              has an expired username/password

    Contains the following instance attributes:
        username (str)        User name for logging into JGI Genomes Portal
        password (str)        Password for the same
        mainlog (logger)      Logging messages formatter and handler
        session (Session)     HTTP Requests session for logging into JGI
        urls (list)           URLs to files to download
        md5s (list)           MD5 hashes of files for integrity checks
        base (str)            Base directory for the data
        to_covert (list)      Files to convert from FASTA to BLAST databases

    Contains the following methods:
        __init__(self, u, p, base, convertonly, verbose):
            Initialize the class with the username, password, base directory,
            whether or not to only convert to databases, and verbosity level.

        sign_on(self):
            Sign on to JGI Genomes Portal with the provided credentials.
            Searches for failed login attempts and expired username and
            password combinations. Returns a requests.Session object.

        get_xml_urls(self):
            Gets the URLs and th MD5s of the CDS files from the XML file from
            Phytozome. Stores these data in `urls' and `md5s' respectively.

        download_file(self, file):
            Fetches a remote file. Uses the requests.Session object to
            authenticate.

        fetch_cds(self):
            Iterates through the urls and md5s instance attributes and
            downloads the appropriate files. Checks the local MD5 against the
            remote MD5 and downloads the remote file if they differ. Appends
            the filenames of each updated file to the `to_convert' attribute.

        convert(self):
            Iterates through the `to_convert' attribute and converts each file
            from a gzipped FASTA file to a BLAST database.
    """
    #   These are common variables for every new Phytozome class
    #   They should not change from instance to instance
    JGI_LOGIN = 'https://signon.jgi.doe.gov/'
    DL_BASE = 'http://genome.jgi.doe.gov'
    XML_URL = 'http://genome.jgi.doe.gov/ext-api/downloads/get-directory'
    XML_DATA = {'organism': 'PhytozomeV10'}
    FAILED_LOGIN = 'Login and password do not match'
    EXPIRED_ACCOUNT = 'Sorry, your password has expired'
    TO_FETCH = phytozome_species.phyto_fetch

    def __init__(self, u, p, base, convertonly, verbose):
        """Initialize the class with the username, password, base directory,
           whether or not to only convert to databases, and verbosity level."""
        self.username = u
        self.password = p
        self.mainlog = set_verbosity.verbosity(__name__, verbose)
        self.mainlog.debug('Creating new instance of Phytozome')
        #   If we are only converting, then we don't have to sign on
        if convertonly:
            self.session = None
        else:
            self.session = self.sign_on()
        self.urls = []
        self.md5s = []
        self.base = base
        self.to_convert = []
        dir_funcs.makebase(base, self.mainlog)
        return

    def sign_on(self):
        """Sign on to JGI Genomes Portal with the provided credentials.
           Searches for failed login attempts and expired username and
           password combinations. Returns a requests.Session object."""
        self.mainlog.debug('Logging in to JGI Genomes Portal with username ' +
                           self.username)
        #   Start a new session, this will store our login information
        session = requests.Session()
        #   This is the data we will send to phytozome
        login_creds = {'login': self.username, 'password': self.password}
        #   Get the response data back - the results of our login attempt
        resp = session.post(self.JGI_LOGIN, data=login_creds)
        if self.FAILED_LOGIN in resp.text:
            self.mainlog.critical('Could not log into JGI Genomes Portal.\
 Check username and password')
            exit(1)
        elif self.EXPIRED_ACCOUNT in resp.text:
            self.mainlog.critical('Your JGI Genomes Portal username and\
 password have expired!')
            exit(1)
        self.mainlog.debug('The page I got back was \n' + resp.text)
        return session

    def get_xml_urls(self):
        """Gets the URLs and th MD5s of the CDS files from the XML file from
           Phytozome. Stores these data in `urls' and `md5s' respectively."""
        self.mainlog.debug('Fetching XML')
        #   This suffix is what we want the filenames ending with
        #   this can change, depending on the target of the LRT
        suffix = '.cds.fa.gz'
        #   Use HTTP GET to fetch the XML from Phytozome's server
        #   This is also a response obkect
        xml = self.session.get(self.XML_URL, params=self.XML_DATA)
        self.mainlog.debug('The XML I got was \n\n' + xml.text)
        #   Create an element tree out of it, so we can easily step
        #   through the data
        xml_tree = ElementTree.fromstring(xml.text)
        #   Step through it and extract all CDS URLs
        for elem in xml_tree.findall('.//file'):
            #   if the URL ends in a certain suffix, then save it
            if elem.attrib.get('url').endswith(suffix):
                url = elem.attrib.get('url')
                md5 = elem.attrib.get('md5')
                #   Check to see that the file is in the list of
                #   species to download
                local_filename = file_funcs.local_name(url)
                species_name = file_funcs.species_name(local_filename)
                if species_name in self.TO_FETCH:
                    self.urls.append(url)
                    self.md5s.append(md5)
        self.mainlog.debug('Found ' + str(len(self.urls)) + ' files to fetch')
        return

    def download_file(self, url):
        """Fetches a remote file. Uses the requests.Session object to
           authenticate."""
        self.mainlog.debug('Fetching ' + url)
        #   With stream=True, it downloads the response right away
        resp = self.session.get(self.DL_BASE + url, stream=True)
        #   Save the file
        with open(file_funcs.local_name(url), 'wb') as f:
            #   Take the file in pieces
            for chunk in resp.iter_content(chunk_size=1024):
                #   Empty chunks are for keepalive
                #   purposes, we don't save those
                if chunk:
                    #   Write the file to disk
                    f.write(chunk)
                    #   and flush the buffer
                    f.flush()
            self.mainlog.debug('Done fetching ' + url)
        return

    #    A function to fetch the CDS files
    def fetch_cds(self):
        """Iterates through the urls and md5s instance attributes and
           downloads the appropriate files. Checks the local MD5 against the
           remote MD5 and downloads the remote file if they differ. Appends
           the filenames of each updated file to the `to_convert' attribute."""
        self.mainlog.debug('Downloading files from ' +
                           str(len(self.urls)) +
                           ' species')
        for u, m in zip(self.urls, self.md5s):
            #   Get a local name of the CDS
            lname = file_funcs.local_name(u)
            #   Get the species name from the filename
            species_name = file_funcs.species_name(lname)
            #   Create the species directory
            target_dir = dir_funcs.make_species_dir(
                self.base,
                species_name,
                self.mainlog)
            #   cd into it
            os.chdir(target_dir)
            #   check to see if the file already exists
            if file_funcs.file_exists(lname, self.mainlog):
                #   Get the md5
                lmd5 = file_funcs.calculate_md5(lname, self.mainlog)
                #   Compare the MD5s
                md5s_same = file_funcs.checksum_is_same(lmd5, m, self.mainlog)
                #   If they are the same, skip it, and move on
                if md5s_same:
                    self.mainlog.info(lname + ' is current. Skipping.')
                    continue
                else:
                    self.mainlog.info(lname + ' is out of date. Downloading.')
                    #   Try to download it until the MD5s check out
                    same = False
                    while not same:
                        self.download_file(u)
                        new_lmd5 = file_funcs.calculate_md5(
                            lname,
                            self.mainlog)
                        same = file_funcs.checksum_is_same(
                            new_lmd5,
                            m,
                            self.mainlog)
                    #   Tack it onto the list of files to convert
                    self.to_convert.append(
                        os.path.join(
                            self.base,
                            target_dir,
                            lname)
                        )
            else:
                self.mainlog.info(lname + ' does not yet exist. Downloading.')
                #   And the same procedure as if the file were updated
                same = False
                while not same:
                    self.download_file(u)
                    new_lmd5 = file_funcs.calculate_md5(
                        lname,
                        self.mainlog)
                    same = file_funcs.checksum_is_same(
                        new_lmd5,
                        m,
                        self.mainlog)
                self.to_convert.append(
                    os.path.join(
                        self.base,
                        target_dir,
                        lname))
        self.mainlog.info('Done downloading CDS files from Phytozome.')
        return

    def convert(self):
        """Iterates through the `to_convert' attribute and converts each file
            from a gzipped FASTA file to a BLAST database."""
        #   What is the path to the makeblastdb executable?
        makeblastdb_path = check_modules.check_executable('makeblastdb')
        #   Check if the list of updated CDS files is empty or not
        if not self.to_convert:
            #   If it is empty, then populate it with all of them
            fname_list = file_funcs.get_file_by_ext(
                self.base,
                '.cds.fa.gz',
                self.mainlog)
        else:
            fname_list = self.to_convert
        #   for each one
        for f in fname_list:
            out, error = format_blast.format_blast(makeblastdb_path, f)
            self.mainlog.info('stdout: \n' + out)
            self.mainlog.info('stderr: \n' + error)
        return
