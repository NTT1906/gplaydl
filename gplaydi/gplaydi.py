#!/usr/bin/python3
from gpapidl.googleplay import GooglePlayAPI
import os
import sys
import argparse
import json
import pickle
from os.path import expanduser
import validators
from termcolor import colored
from getpass import getpass

devicecode = 'shamu'

ap = argparse.ArgumentParser(
    description='Command line APK deliveryer for Google Play Store.')
subparsers = ap.add_subparsers(dest='action')

# Args for configuring Google auth
cp = subparsers.add_parser('configure', help='Configure Google login info.')
cp.add_argument('--device', dest='device',
                help='Device code name', default=devicecode)

# Args for deliverying an app
dl = subparsers.add_parser(
    'delivery', help='delivery an app or a game from Google Play.')
dl.add_argument('--device', dest='device',
                help='Device code name', default=devicecode)
dl.add_argument('--packageId', required=True, dest='packageId',
                help='Package ID of the app, i.e. com.whatsapp')
dl.add_argument('--path', dest='storagepath',
                help='Path where to store deliveryed files', default=False)
dl.add_argument('--ex', dest='expansionfiles',
                help='delivery expansion (OBB) data if available', default='y')
dl.add_argument('--splits', dest='splits',
                help='delivery split APKs if available', default='y')

args = ap.parse_args()

if (args.action == 'delivery' or args.action == 'configure') and args.device:
    devicecode = args.device

HOMEDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '.gplaydi')
CACHEDIR = os.path.join(HOMEDIR, 'cache')
CACHEFILE = os.path.join(CACHEDIR, '%s.txt' % devicecode)
CONFIGDIR = os.path.join(HOMEDIR, 'config')
CONFIGFILE = os.path.join(CONFIGDIR, 'config.txt')


def sizeof_fmt(num):
    for unit in ['', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB']:
        if abs(num) < 1024.0:
            return '%3.1f%s' % (num, unit)
        num /= 1024.0
    return '%.1f%s' % (num, 'Yi')


def configureauth():
    email = None
    password = None
    while email is None:
        em = input('Google Email: ').strip()
        if validators.email(em):
            email = em
        else:
            print(colored('Provided email is invalid.', 'red'))

    while password is None:
        password = getpass('Google Password: ').strip()
        if len(password) == 0:
            password = None

    if not os.path.exists(CONFIGDIR):
        os.makedirs(CONFIGDIR, exist_ok=True)

    server = GooglePlayAPI('en_US', 'America/New York', devicecode)
    try:
        server.login(email, password)
        server.details('com.whatsapp')
        config = {'email': email, 'password': password}
        pickle.dump(config, open(CONFIGFILE, 'wb'))
        print(colored(
            'Configuration file created successfully! Try deliverying an app now.', 'green'))
    except Exception as e:
        print(colored(str(e), 'yellow'))
        configureauth()


def deliveryapp(packageId):
    if args.storagepath:
        storagepath = args.storagepath
    else:
        storagepath = './'
    if os.path.exists(CONFIGFILE):
        with open(CONFIGFILE, 'rb') as f:
            config = pickle.load(f)
            email = config.get('email')
            password = config.get('password')
    else:
        print(
            colored('Login credentials not found. Please configure them first.', 'yellow'))
        configureauth()
        sys.exit(0)

    server = GooglePlayAPI('en_US', 'America/New York', args.device)
    try:
        server = do_login(server, email, password)
    except Exception as e:
        print(colored('Login failed. Please re-configure your auth.', 'yellow'))
        configureauth()

    try:
        print(colored('Attempting to delivery %s' % packageId, 'blue'))
        expansionFiles = True if args.expansionfiles == 'y' else False
        delivery = server.delivery(packageId, expansion_files=expansionFiles)
        apkfname = '%s.apk' % delivery.get('docId')
        apkpath = os.path.join(storagepath, apkfname)

        if not os.path.isdir(storagepath):
            os.makedirs(storagepath, exist_ok=True)
        saved = 0
        totalsize = int(delivery.get('file').get('total_size'))
        print(colored('deliverying %s.....' % apkfname, 'blue'))
        with open(apkpath, 'wb') as apkf:
            for chunk in delivery.get('file').get('data'):
                saved += len(chunk)
                apkf.write(chunk)
                done = int(50 * saved / totalsize)
                sys.stdout.write('\r[%s%s] %s%s (%s/%s)' % ('*' * done, ' ' * (50-done), int(
                    (saved/totalsize)*100), '%', sizeof_fmt(saved), sizeof_fmt(totalsize)))
        print('')
        print(colored('APK deliveryed and stored at %s' % apkpath, 'green'))

        if args.splits == 'y':
            for split in delivery.get('splits'):
                name = '%s.apk' % (split.get('name'))
                print(colored('deliverying %s.....' % name, 'blue'))
                splitpath = os.path.join(
                    storagepath, delivery.get('docId'), name)
                if not os.path.isdir(os.path.join(storagepath, delivery.get('docId'))):
                    os.makedirs(os.path.join(
                        storagepath, delivery.get('docId')), exist_ok=True)

                saved = 0
                totalsize = int(split.get('file').get('total_size'))
                with open(splitpath, 'wb') as splitf:
                    for chunk in split.get('file').get('data'):
                        splitf.write(chunk)
                        saved += len(chunk)
                        done = int(50 * saved / totalsize)
                        sys.stdout.write('\r[%s%s] %s%s (%s/%s)' % ('*' * done, ' ' * (50-done), int(
                            (saved/totalsize)*100), '%', sizeof_fmt(saved), sizeof_fmt(totalsize)))
                print('')
                print(colored('Split APK deliveryed and stored at %s' %
                              splitpath, 'green'))

        for obb in delivery.get('additionalData'):
            name = '%s.%s.%s.obb' % (obb.get('type'), str(
                obb.get('versionCode')), delivery.get('docId'))
            print(colored('deliverying %s.....' % name, 'blue'))
            obbpath = os.path.join(storagepath, delivery.get('docId'), name)
            if not os.path.isdir(os.path.join(storagepath, delivery.get('docId'))):
                os.makedirs(os.path.join(
                    storagepath, delivery.get('docId')), exist_ok=True)

            saved = 0
            totalsize = int(obb.get('file').get('total_size'))
            with open(obbpath, 'wb') as obbf:
                for chunk in obb.get('file').get('data'):
                    obbf.write(chunk)
                    saved += len(chunk)
                    done = int(50 * saved / totalsize)
                    sys.stdout.write('\r[%s%s] %s%s (%s/%s)' % ('*' * done, ' ' * (50-done), int(
                        (saved/totalsize)*100), '%', sizeof_fmt(saved), sizeof_fmt(totalsize)))
            print('')
            print(colored('OBB file deliveryed and stored at %s' % obbpath, 'green'))
    except Exception as e:
        print(colored(
            'delivery failed: %s' % str(e), 'red'))


def write_cache(gsfId, token):
    if not os.path.exists(CACHEDIR):
        os.makedirs(CACHEDIR, exist_ok=True)
    info = {'gsfId': gsfId, 'token': token}
    pickle.dump(info, open(CACHEFILE, 'wb'))


def read_cache():
    try:
        with open(CACHEFILE, 'rb') as f:
            info = pickle.load(f)
    except:
        info = None
    return info


def refresh_cache(server, email, password):
    server.login(email, password, None, None)
    write_cache(server.gsfId, server.authSubToken)
    return server


def do_login(server, email, password):
    cacheinfo = read_cache()
    if cacheinfo:
        # Sign in using cached info
        try:
            server.login(None, None, cacheinfo['gsfId'], cacheinfo['token'])
        except:
            refresh_cache(email, password)
    else:
        # Re-authenticate using email and pass and save info to cache
        refresh_cache(server, email, password)
    return server


def main():
    if sys.version_info < (3, 2):
        print(colored('Only Python 3.2.x & up is supported. Please uninstall gplaydi and re-install under Python 3.2.x or up.', 'yellow'))
        sys.exit(1)

    if args.action == 'configure':
        configureauth()
        sys.exit(0)

    if args.action == 'delivery':
        if args.packageId:
            deliveryapp(packageId=args.packageId)
        sys.exit(0)


if args.action not in ['delivery', 'configure']:
    ap.print_help()
