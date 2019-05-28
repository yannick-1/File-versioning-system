#!/usr/bin/env python

from __future__ import with_statement

import logging
import sys
import errno
import os.path
from os.path import exists
from os.path import dirname
from os.path import basename
from glob import glob
import re
from shutil import copy2
from shutil import rmtree
from shutil import copyfile
import filecmp
import collections

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn


class VersionFS(LoggingMixIn, Operations):
    def __init__(self):
        # get current working directory as place for versions tree
        self.root = os.path.join(os.getcwd(),'.versiondir')
        self.mount = os.path.join(os.getcwd(),'mount')          ##  ../mount       
        self.versionDictionary = dict() ##  keeps track of exisitng verisons
        self.versionDicdionary = collections.OrderedDict()
        self.versionList = list() ##  keeps track of exisitng verisons
        # check to see if the versions directory already exists
        if os.path.exists(self.root):
            print 'Version directory already exists.'
        else:
            print 'Creating version directory.'
            os.mkdir(self.root)

    # Helpers

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    # Filesystem methods

    def access(self, path, mode):
        # print "access:", path, mode
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        # print "chmod:", path, mode
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        # print "chown:", path, uid, gid
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        # print "getattr:", path
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        # print "readdir:", path
        full_path = self._full_path(path)
        dirents = ['.', '..']
        if os.path.isdir(full_path):
            # shownFiles = os.listdir(full_path)
            for e in os.listdir(full_path):
                if (e[-2] not in '.'): dirents.append(e)   
        for r in dirents:
            yield r

    def readlink(self, path):
        # print "readlink:", path
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        # print "mknod:", path, mode, dev
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        # print "rmdir:", path
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        # print "mkdir:", path, mode
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        # print "statfs:", path
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        # print "unlink:", path
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        # print "symlink:", name, target
        return os.symlink(target, self._full_path(name))

    def rename(self, old, new):
        # print "rename:", old, new
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        # print "link:", target, name
        return os.link(self._full_path(name), self._full_path(target))

    def utimens(self, path, times=None):
        # print "utimens:", path, times
        return os.utime(self._full_path(path), times)

    # File methods

    def open(self, path, flags):
        print '** open:', path, '**'
        full_path = self._full_path(path)
        tempFile = full_path + ".0"
        copyfile(full_path,tempFile)
        # tempFile = dirname(full_path) + "/." + basename(full_path) + ".0";
        # if not exists(tempFile):
        #     f = open(tempFile,'w');      

        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        print '** create:', path, '**'
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        print '** read:', path, '**'
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        print '** write:', path, '**'
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        print '** truncate:', path, '**'
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        print '** flush', path, '**'
        return os.fsync(fh)

    def release(self, path, fh):
        print '** release', path, '**'
        # self.version_iterator(path)
        fname = path
        temp = self._full_path(fname) + '.'
        if not self.versionDictionary.has_key(fname):
            self.versionDictionary.setdefault(fname,1)
        elif not filecmp.cmp(self._full_path(fname),self._full_path(fname+'.1')):
            versionNum = self.versionDictionary.get(fname)
            if (versionNum<6): versionNum += 1
            self.versionDictionary[fname] = min(versionNum,6)
            for versionNum in range(versionNum,1,-1):
                copyfile(temp+str(versionNum-1),temp+str(versionNum))  
        temp = temp + '1'
        copyfile(self._full_path(fname),temp)        
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        print '** fsync:', path, '**'
        return self.flush(path, fh)

def main(mountpoint):
    FUSE(VersionFS(), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1])
