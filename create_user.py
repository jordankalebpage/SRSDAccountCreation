#!/usr/bin/env python
import datetime
import getpass
import glob
import logging
import os.path
import string
import sys
from collections import deque
from logging.handlers import RotatingFileHandler
from random import randint, SystemRandom
from re import compile
from subprocess import call

import pysftp
# installed dependencies
import requests
from ldap3 import Server, Connection, NONE, SUBTREE
from profanityfilter import ProfanityFilter

# *** Add any potential chromebook enrollment accounts here if necessary. e.g., PK3 or PK4
EXCLUSION_LIST = ('PK3', 'PK4', '00', '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th', '11th',
                  '12th', 'billybob')

# ***
SFTP_HOST = '############'
SFTP_USERNAME = '############'
SFTP_PASSWORD = '############'

LDAP_HOST = '############'
LDAP_USERNAME = '############'
LDAP_PASSWORD = '############'


TESTING = False


# Class to contain Student information
class Student:
    def __init__(self, first_name, last_name, birthday, student_id, grade_level, building_number,
                 email=None, password=None, username=None, needs_password=False):
        self.fullname = first_name + ' ' + last_name
        self.first_name = first_name
        self.last_name = last_name
        self.birthday = birthday
        self.student_id = student_id
        self.grade_level = grade_level
        self.building_number = building_number
        self.is_sro_student = (building_number == "615")

        if self.grade_level == 'PK3':
            self.graduation_year = datetime.date.today().year + 14
        elif self.grade_level == 'PK4':
            self.graduation_year = datetime.date.today().year + 13
        else:
            self.graduation_year = (datetime.date.today().year + (12 - int(grade_level)))
        
        if datetime.date.today().month >= 8 and datetime.date.today().month <= 12:
            self.graduation_year += 1

        self.email = email
        self.password = generate_password() if needs_password is True else password
        self.parent_username = str(excel_date(birthday)) + self.first_name[:3].lower()
        self.username = username

    def __eq__(self, other):
        return (self.username == other.username) and (self.password == other.password)

    def __repr__(self):
        rep = 'Student(' + 'Username: ' + self.username + ', ' + 'First Name: ' + self.first_name + ', '\
              + 'Last Name: ' + self.last_name + ')'
        return rep

    def set_username(self, username):
        self.username = username

    def set_email(self):
        self.email = self.username + '@xyz.org'
# End Student Class


# Class to handle interfacing between SIS and LDAP users
class Interface:
    def __init__(self):
        self.sis_user_list = []
        self.sis_usernames = []
        self.ldap_user_list = []

        self.gradepk3_user_list = []
        self.gradepk4_user_list = []
        self.grade00_user_list = []
        self.grade01_user_list = []
        self.grade02_user_list = []
        self.grade03_user_list = []
        self.grade04_user_list = []
        self.grade05_user_list = []
        self.grade06_user_list = []
        self.grade07_user_list = []
        self.grade08_user_list = []
        self.grade09_user_list = []
        self.grade10_user_list = []
        self.grade11_user_list = []
        self.grade12_user_list = []

        self.sro_student_list = []

        self.needs_username_list = []
        self.needs_ldap_account_list = []
        self.needs_ldap_deletion_list = []

        self.new_web_id = dict()

        self.file_locations = dict()

        self.conn = None

    def _print_all_info(self):
        logging.debug('')

        logging.debug(f'All SIS users: {self.sis_user_list}')
        logging.debug(f'All LDAP users: {self.ldap_user_list}')
        logging.debug(f'All SRO-Student users: {self.sro_student_list}')

        logging.debug(f'All PK3 users: {self.gradepk3_user_list}')
        logging.debug(f'All PK4 users: {self.gradepk4_user_list}')

        logging.debug(f'All Grade-00 users: {self.grade00_user_list}')
        logging.debug(f'All Grade-01 users: {self.grade01_user_list}')
        logging.debug(f'All Grade-02 users: {self.grade02_user_list}')
        logging.debug(f'All Grade-03 users: {self.grade03_user_list}')
        logging.debug(f'All Grade-04 users: {self.grade04_user_list}')
        logging.debug(f'All Grade-05 users: {self.grade05_user_list}')
        logging.debug(f'All Grade-06 users: {self.grade06_user_list}')
        logging.debug(f'All Grade-07 users: {self.grade07_user_list}')
        logging.debug(f'All Grade-08 users: {self.grade08_user_list}')
        logging.debug(f'All Grade-09 users: {self.grade09_user_list}')
        logging.debug(f'All Grade-10 users: {self.grade10_user_list}')
        logging.debug(f'All Grade-11 users: {self.grade11_user_list}')
        logging.debug(f'All Grade-12 users: {self.grade12_user_list}')

        logging.debug(f'Needs usernames: {self.needs_username_list}')
        logging.debug(f'Needs LDAP creation: {self.needs_ldap_account_list}')
        logging.debug(f'Needs LDAP deletion: {self.needs_ldap_deletion_list}')

        logging.debug(f'Info and ctl file pairings: {self.file_locations}')

        logging.debug('')

    def get_usernames_from_sftp(self) -> None:
        global TESTING
        if not TESTING:
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None

            srv = pysftp.Connection(host=SFTP_HOST, username=SFTP_USERNAME, password=SFTP_PASSWORD, port=22,
                                    cnopts=cnopts)
            srv.get('/Steve/student.csv', preserve_mtime=True)

            srv.close()

        sis_user_list_path = os.path.join(os.getcwd(), 'student.csv')
        sis_user_list = []
        needs_username_list = []
        wrong_web_id = []
        pattern = compile(r'^\d\d[a-zA-Z]{2,6}')

        with open(sis_user_list_path, mode='r', encoding='utf-8') as f:
            for line in f.readlines():
                first_name = str(line.split(',')[0]).title()
                last_name = str(line.split(',')[1]).title()
                curr_username = str(line.split(',')[2]).lower()
                curr_grade = str(line.split(',')[3]).strip()
                birthday = str(line.split(',')[4]).strip()
                student_id = str(line.split(',')[5]).strip()
                building_number = str(line.split(',')[6]).strip()

                curr_student = Student(first_name=first_name, last_name=last_name, birthday=birthday,
                                       student_id=student_id, grade_level=curr_grade, username=curr_username,
                                       building_number=building_number)

                if int(curr_student.grade_level) < -2:
                    continue

                if int(curr_student.grade_level) == -1:
                    curr_student.grade_level = 'PK4'
                elif int(curr_student.grade_level) == -2:
                    curr_student.grade_level = 'PK3'

                if "'" in curr_student.username:
                    curr_student.username = curr_student.username.replace("'", "")
                if " " in curr_student.username:
                    curr_student.username = curr_student.username.replace(" ", "")

                if curr_student.username == '':
                    needs_username_list.append(curr_student)
                elif not pattern.fullmatch(curr_student.username):
                    wrong_web_id.append(curr_student)
                else:
                    sis_user_list.append(curr_student)
                    self.sis_usernames.append(curr_student.username)

                if curr_student.is_sro_student:
                    self.sro_student_list.append(curr_student)
                elif curr_student.grade_level == 'PK3':
                    self.gradepk3_user_list.append(curr_student)
                elif curr_student.grade_level == 'PK4':
                    self.gradepk4_user_list.append(curr_student)
                elif curr_student.grade_level == '0':
                    self.grade00_user_list.append(curr_student)
                elif curr_student.grade_level == '1':
                    self.grade01_user_list.append(curr_student)
                elif curr_student.grade_level == '2':
                    self.grade02_user_list.append(curr_student)
                elif curr_student.grade_level == '3':
                    self.grade03_user_list.append(curr_student)
                elif curr_student.grade_level == '4':
                    self.grade04_user_list.append(curr_student)
                elif curr_student.grade_level == '5':
                    self.grade05_user_list.append(curr_student)
                elif curr_student.grade_level == '6':
                    self.grade06_user_list.append(curr_student)
                elif curr_student.grade_level == '7':
                    self.grade07_user_list.append(curr_student)
                elif curr_student.grade_level == '8':
                    self.grade08_user_list.append(curr_student)
                elif curr_student.grade_level == '9':
                    self.grade09_user_list.append(curr_student)
                elif curr_student.grade_level == '10':
                    self.grade10_user_list.append(curr_student)
                elif curr_student.grade_level == '11':
                    self.grade11_user_list.append(curr_student)
                elif curr_student.grade_level == '12':
                    self.grade12_user_list.append(curr_student)
            f.close()

        logging.info('')
        logging.info('Student list successfully obtained via SFTP.')

        logging.info('Students who need SIS usernames: ')
        if len(needs_username_list) == 0:
            logging.info('None')
        else:
            for student in needs_username_list:
                logging.info(student.first_name + ' ' + student.last_name + ', Grade ' + str(student.grade_level))
            logging.info('')

        logging.info("Students with incorrect web ID's: ")
        if len(wrong_web_id) == 0:
            logging.info('None')
        else:
            for student in wrong_web_id:
                logging.info(student.username)
            logging.info('')

        if len(wrong_web_id) > 0:
            new_web_id = dict()
            for student in wrong_web_id:
                new_web_id[student.username] = resolve_username(student.username, self.sis_usernames,
                                                                student.first_name,
                                                                student.last_name,
                                                                student.graduation_year,
                                                                'student')

            logging.info("Recommended new web ID's: ")
            for curr_student_username, recommended_student_username in new_web_id.items():
                logging.info(f'Current username: {curr_student_username}\t|\tRecommended username:'
                             f' {recommended_student_username}')
            logging.info('')

        self.sis_user_list = sis_user_list
        self.needs_username_list = needs_username_list

    def create_usernames(self) -> None:
        for student in self.needs_username_list[:]:
            student.username = resolve_username(student.username, self.sis_usernames, student.first_name,
                                                student.last_name, student.graduation_year)
            self.needs_username_list.remove(student)
            self.sis_user_list.append(student)
            self.sis_usernames.append(student.username)

    def create_emails_and_passwords(self) -> None:
        for student in self.needs_ldap_account_list:
            student.set_email()
            logging.info(f'Generating password for: {student.username}')
            student.password = generate_password()

    def open_ldap_connection(self) -> None:
        server = Server(host=LDAP_HOST, port=636, use_ssl=True, get_info=NONE)
        login_name = LDAP_USERNAME
        password = LDAP_PASSWORD
        attempts = 0

        conn = Connection(server, user='cn=' + login_name + ',o=xyz', password=password)
        conn.bind()

        while conn.result['description'] == 'invalidCredentials':
            logging.info('Incorrect username or password. Please try again.')
            logging.info('Please enter your LDAP username: ')
            login_name = str(input())
            password = getpass.getpass()
            attempts += 1
            if attempts >= 3:
                logging.debug('Exceeded login attempts')
                sys.exit(0)
            conn = Connection(server, user='CN=' + login_name + ',o=xyz', password=password)
            conn.bind()

        self.conn = conn
        logging.info('LDAP Connection has been opened.')
        logging.debug(f'LDAP Connection opened on {LDAP_HOST}')

    def close_ldap_connection(self) -> None:
        if self.conn is not None:
            self.conn.unbind()
            logging.info('LDAP Connection has been closed.')
        else:
            logging.debug('LDAP Connection is already closed.')

    def get_students_from_ldap(self) -> None:
        if self.conn is None:
            self.open_ldap_connection()

        search_filter = '(objectclass=Person)'

        # Get the PK Students
        for i in range(3, 5):
            curr_grade = 'Grade-PK' + str(i)
            search_base = 'ou=' + curr_grade + ',o=xyz'
            logging.info('Searching ' + curr_grade)
            self.conn.search(search_base=search_base,
                             search_filter=search_filter,
                             search_scope=SUBTREE,
                             attributes=['uid'])

            for entry in self.conn.entries:
                uid = entry['uid'].value
                if uid not in EXCLUSION_LIST:
                    self.ldap_user_list.append(uid.lower())

        # Get the non-PK Students
        for i in range(0, 13):
            curr_grade = 'Grade-' + str(i).zfill(2)
            search_base = 'ou=' + curr_grade + ',o=xyz'
            logging.info('Searching ' + curr_grade)
            self.conn.search(search_base=search_base,
                             search_filter=search_filter,
                             search_scope=SUBTREE,
                             attributes=['uid'])

            for entry in self.conn.entries:
                uid = entry['uid'].value
                if uid not in EXCLUSION_LIST:
                    self.ldap_user_list.append(uid.lower())

        # Get the SRO Students
        search_base = 'ou=SRO-Student' + ',o=xyz'
        logging.info('Searching ' + 'SRO-Student')
        self.conn.search(search_base=search_base,
                         search_filter=search_filter,
                         search_scope=SUBTREE,
                         attributes=['uid'])

        for entry in self.conn.entries:
            uid = entry['uid'].value
            if uid not in EXCLUSION_LIST:
                self.ldap_user_list.append(uid.lower())

        self.ldap_user_list.sort()
        logging.info('')
        logging.info(str(len(self.ldap_user_list)) + ' total students in LDAP, Grades PK3-12 and SRO-Student.')

    def compare_sis_and_ldap(self) -> None:
        logging.info('Comparing the SIS and LDAP lists')
        # If a student is in Edirectory but no longer in sis, we can delete them
        with open('ldap_user_list.log', mode='w') as file:
            for student in self.ldap_user_list:
                file.write(student + '\n')
                if student not in self.sis_usernames:
                    self.needs_ldap_deletion_list.append(student)
            file.close()

        # If a student is in SIS but not in Edirectory yet, we need to add them
        for student in self.sis_user_list:
            if student.username not in self.ldap_user_list:
                self.needs_ldap_account_list.append(student)
                
        # print(f'Accounts needing deletion: {self.needs_ldap_deletion_list}')

    def delete_ldap_accounts(self) -> None:
        if len(self.needs_ldap_deletion_list) == 0:
            logging.info('No accounts need to be deleted.')
        else:
            logging.info(f'Number of accounts needing deletion: {str(len(self.needs_ldap_deletion_list))}')
            error_count = 0
            # User exists in LDAP but not PowerSchool -> we can delete them from LDAP
            for student in self.needs_ldap_deletion_list:
                self.conn.search(search_base='o=xyz',
                                 search_filter='(uid=' + student + ')')
                user = self.conn.entries[0].entry_dn
                self.conn.delete(user)
                if str(self.conn.result['description']) == 'success':
                    logging.info('Success - ' + student + ' deleted.')
                else:
                    logging.info('Error - ' + student + ' could not be deleted.')
                    error_count += 1
                logging.info('\n')
            logging.info('\nAccount deletion process completed with ' + str(error_count) + ' errors.')

    def update_students_in_sftp(self) -> None:
        if len(self.needs_ldap_account_list) == 0:
            logging.info('No students need to be updated in SFTP.')
            return
        
        logging.info('Updating new students file in SFTP')
        directory = os.getcwd()
        filename = os.path.join(directory, 'new_stds.txt')

        # *** Make this Append or Overwrite?
        with open(filename, mode='w+') as new_stds:
            for student in self.needs_ldap_account_list:
                new_stds.write(student.student_id)
                new_stds.write('\t')
                new_stds.write(student.parent_username)
                new_stds.write('\t')
                new_stds.write(student.student_id)
                new_stds.write('\t')
                new_stds.write('1')
                new_stds.write('\t')
                new_stds.write(student.username)
                new_stds.write('\t')
                new_stds.write(student.password)
                new_stds.write('\t')
                new_stds.write('1')
                new_stds.write('\t')
                new_stds.write(student.student_id)
                new_stds.write('\n')

            new_stds.close()

        global TESTING
        if not TESTING:
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None

            srv = pysftp.Connection(host=SFTP_HOST, username=SFTP_USERNAME, password=SFTP_PASSWORD, port=22,
                                    cnopts=cnopts)
            srv.put(filename, '/Steve/new_stds.txt', preserve_mtime=True)
            logging.info('New student file successfully updated in SFTP')
            srv.close()

    # Return false if the potential username is in ldap already, return true otherwise
    # cn = username, ou = Grade##, o = xyz
    def check_name_in_ldap(self, candidate) -> bool:
        if self.conn is None:
            self.open_ldap_connection()

        self.conn.search(search_base='o=xyz', search_filter='(uid=' + candidate + ')')
        if len(self.conn.entries) > 0:
            logging.info('Username exists in LDAP: ')
            logging.info(self.conn.entries[0])
            return False
        logging.info('Username not found in LDAP.')
        return True
    
    def check_sro_correct_ou(self, student) -> bool:
        if self.conn is None:
            self.open_ldap_connection()
        
        with open('SRO Students in wrong context.txt',  mode='a+') as f:
            self.conn.search(search_base='o=xyz', search_filter='(uid=' + student.username + ')', attributes=['ou'])
            if len(self.conn.response) > 0:
                # logging.info('Username exists in LDAP: ')
                if student.is_sro_student and (self.conn.response[0]['dn'].split(',')[1][3:] != 'SRO-Student'):
                    logging.info(f'{student.username} is an SRO Student and not in the correct context')
                    logging.info(self.conn.response[0])
                    f.write(f'{student.username}: {self.conn.response[0]}' + '\n')
                return False
            # logging.info('Username not found in LDAP.')
            return True

    def make_info_and_ctl_files(self):
        info_path = 'c:\\jrb\\account_info'
        ctl_path = 'c:\\jrb\\dynamic_ctl_file'

        ctl_template = ['\t\tSEPARATOR=,', '\t\tSet Universal Passwords=y', '\t\tUSER TEMPLATE=Y',
                        '\t\tUse two passes=Y',
                        'FIELDS', '\tPassword',
                        '\tName', '\tFull Name', '\tLast Name', '\tGiven Name', '\tInternet Email Address']

        # Make the directory if it doesn't exist
        if not os.path.exists('c:\\jrb'):
            os.makedirs('c:\\jrb')

        # Delete all of the previous account info files, so that we only have accounts that need to be added
        for filename in glob.glob(info_path + '*'):
            try:
                os.remove(filename)
            except OSError:
                logging.info('File ' + filename + ' is currently in use. Close the file and try again.')

        # Delete all of the previous ctl files, so that we only have accounts that need to be added
        for filename in glob.glob('c:\\jrb\\dynamic_ctl_file*'):
            try:
                os.remove(filename)
            except OSError:
                logging.info('File ' + filename + ' is currently in use. Close the file and try again.')

        for student in self.needs_ldap_account_list:
            information = [student.password, student.username, student.fullname,
                           student.last_name, student.first_name, student.email]
            # logging.debug(f'{information}')

            if student.is_sro_student:
                new_info_path = info_path + '_SRO-Student.dat'
                new_ctl_path = ctl_path + '_SRO-Student.ctl'
                name_context = '\t\tNAME CONTEXT="' + '.SRO-Student.xyz"\n'

                grade = 'SRO-Student'
            else:
                str_grade = str(student.grade_level).zfill(2)
                new_info_path = info_path + '_Grade-' + str_grade + '.dat'
                new_ctl_path = ctl_path + '_Grade-' + str_grade + '.ctl'
                name_context = '\t\tNAME CONTEXT="' + '.Grade-' + str_grade + '.xyz"\n'

                grade = 'Grade' + str_grade

            if os.path.exists(new_info_path):
                with open(new_info_path, mode='a') as f:
                    f.write(','.join(information) + '\n')
            else:
                with open(new_info_path, mode='w') as f:
                    f.write(','.join(information) + '\n')

            if not os.path.exists(new_ctl_path):
                with open(new_ctl_path, mode='w') as dynamic_file:
                    dynamic_file.write('IMPORT CONTROL\n')
                    dynamic_file.write(name_context)
                    dynamic_file.write('\n'.join(ctl_template))

            self.file_locations[grade] = self.file_locations.get(grade, {'info_path': new_info_path,
                                                                         'ctl_path': new_ctl_path})

    # Create user accounts through JRButils using a ctl file and account info file
    def import_using_jrb(self) -> None:
        for k, v in self.file_locations.items():
            logging.debug(f'Key: {k}')
            ctl_path = v.get('ctl_path')
            info_path = v.get('info_path')
            call(['c:\\jrb\\Part_4\\jrbimprt.exe', ctl_path, info_path,
                  '/$', '/e', '/v', '/x=10'])
# End Interface Class


def resolve_username(curr_username, username_list, first_name, last_name, graduation_year, category='student') -> str:
    last_name_partition = last_name
    num_attempts = 0

    logging.debug(username_list)

    if curr_username is None or curr_username == '':
        first_name_split = split_name(first_name)
        last_name_split = split_name(last_name)

        if len(last_name_split) >= 5:
            curr_username = (str(graduation_year)[2:] + last_name_split[:5] + first_name_split[0]).lower()
            last_name_partition = last_name_split[:5]
            first_name_partition = first_name[:6 - len(last_name_partition)]
        else:
            curr_username = (str(graduation_year)[2:] + last_name_split + first_name_split[0]).lower()
            last_name_partition = last_name_split
            first_name_partition = first_name[:6 - len(last_name_partition)]

        logging.debug('Current Username: ' + curr_username)

    if category == 'student':
        # while search(username_list, curr_username) is not None:
        while curr_username in username_list:
            logging.info('')
            logging.info('Username ' + curr_username + ' exists.')

            # extreme edge case - all possible usernames are taken
            if num_attempts > 15:
                logging.info('Username could not be resolved.')
                sys.exit(1)

            if len(curr_username) < 8:
                last_name_partition = last_name_partition[:-1]
                first_name_partition = first_name[:6 - len(last_name_partition)]
                curr_username = (str(graduation_year)[2:] + last_name_partition + first_name_partition).lower()
                # curr_username = str(graduation_year)[2:] + last_name[:-1] + first_name[:8 - len(curr_username)]
            else:
                last_name_partition = last_name_partition[:-1]
                first_name_partition = first_name[:6 - len(last_name_partition)]
                curr_username = (str(graduation_year)[2:] + last_name_partition + first_name_partition).lower()

            num_attempts += 1
    else:
        while curr_username in username_list:
            logging.info('')
            logging.info('Username ' + curr_username + ' exists.')

            # extreme edge case - all possible usernames are taken
            if num_attempts > 15:
                logging.info('Username could not be resolved.')
                sys.exit(1)

            if len(curr_username) < 8:
                curr_username = last_name[:4] + first_name[:4]
            else:
                last_name_partition = last_name_partition[:-1]
                first_name_partition = first_name[:8 - len(last_name_partition)]
                curr_username = last_name_partition = first_name_partition

            num_attempts += 1

    logging.info('Successful candidate username: ' + curr_username)
    return curr_username


# Rather than pulling the word list from the website every time,
# it would be much faster to just read the list from a local txt file.
# make_word_file opens the word list file if it exists, and makes the
# file if it doesn't exist.
# returns the list of possible words
def make_word_file() -> list:
    word_list_path = 'C:\\Student Acct Management\\SRSDAccountCreation-master\\word_list.txt'

    try:
        f = open(word_list_path)
        word_list = f.readlines()
        f.close()
    except FileNotFoundError:
        logging.info("File not found. Generating word list file...")
        word_site = "https://svnweb.freebsd.org/csrg/share/dict/words?view=co&content-type=text/plain"
        response = requests.get(word_site, headers={'User-Agent': 'Custom'})
        word_list = response.content.splitlines()

        for i in range(0, len(word_list)):
            word_list[i] = word_list[i].decode('utf-8')

        with open(word_list_path, mode='w+', encoding='utf-8') as f:
            f.write('\n'.join(word_list))

    return word_list


# Simply checks a given name to see if it only contains
# alphabetical characters, hyphens, spaces, or apostrophes
def check_name(name) -> bool:
    allowed_chars = string.ascii_letters + "'- "
    if name == '':
        return False

    for letter in name:
        if letter in allowed_chars:
            continue
        else:
            return False

    return True


# Ensure that the given first or last name splits before a hyphen, space, or apostrophe
def split_name(name) -> str:
    return name.split(None, 1)[0]


def generate_password() -> str:
    word_list = make_word_file()

    secure_random = SystemRandom()
    first_word = secure_random.choice(word_list).strip()
    second_word = secure_random.choice(word_list).strip()

    # check if the password is either too long or contains profanity
    pf = ProfanityFilter()
    while len(first_word + second_word) > 10 or len(first_word + second_word) < 6 or \
            "'" in first_word or "'" in second_word or pf.is_profane(first_word) or pf.is_profane(second_word):
        first_word = secure_random.choice(word_list).strip()
        second_word = secure_random.choice(word_list).strip()

    pwd = (first_word + second_word + str(randint(0, 9)) + str(randint(0, 9)))
    return pwd


# Generates a parent's username by converting student's birthday to Excel ordinal
def excel_date(date) -> int:
    temp = datetime.datetime(1899, 12, 31)
    delta = datetime.datetime.strptime(date, '%m/%d/%Y') - temp
    return int(delta.days) + int(int(delta.seconds) / 86400) + 1


# main function
def create_user():
    while True:
        logging.info('\n')
        logging.info('1) Run the manual student creation utility ' +
                     '(creates student in LDAP. Will have to be manually added to SIS)')
        logging.info('2) Run the automated student creation/deletion utility (also updates student info in SIS)')
        logging.info('3) Quit')
        # menu_prompt = int(input().strip())
        menu_prompt = 2

        if menu_prompt == 1:
            # print("Are you creating a student or staff account?: ")
            # user_prompt = input().lower().strip()
            # delete the line below if staff is implemented
            user_prompt = "student"

            if not (user_prompt == "student") and not (user_prompt == "staff"):
                logging.info("You must enter either student or staff.")
                continue
            else:
                if user_prompt == "student":
                    student_information_list = deque([])
                    grade_level_list = deque([])
                    information, grade_levels = create_student(student_information_list, grade_level_list)
                # else:
                #     create_staff()

                logging.info("\nWould you like to create another account?(y/n): ")
                user_prompt = input().lower().strip()
                while not ((user_prompt == 'y') or (user_prompt == 'yes') or
                           (user_prompt == 'n') or (user_prompt == 'no')):
                    logging.info("You must enter y, yes, n, or no.")
                    logging.info("Would you like to create another account?(y/n): ")
                    user_prompt = input().lower().strip()
                if (user_prompt == 'y') or (user_prompt == 'yes'):
                    continue
                elif (user_prompt == 'n') or (user_prompt == 'no'):
                    # Finally add the students that we created through this program to LDAP
                    make_info_files(information, grade_levels)
                    make_dynamic_ctl_files(grade_levels)
                    import_using_jrb()
        elif menu_prompt == 2:
            interface = Interface()
            interface.open_ldap_connection()

            interface.get_usernames_from_sftp()
            interface.create_usernames()

            interface.get_students_from_ldap()
            interface.compare_sis_and_ldap()

            interface.delete_ldap_accounts()

            interface.create_emails_and_passwords()

            interface.update_students_in_sftp()

            interface.make_info_and_ctl_files()

            interface.import_using_jrb()

            interface._print_all_info()

            interface.close_ldap_connection()
            sys.exit(0)
        elif menu_prompt == 3:
            sys.exit(0)
        else:
            logging.info('Only 1, 2, or 3 may be entered.')
            continue


# set up logging and the rotating file handler, then call main function create_user()
if __name__ == '__main__':
    log_formatter = logging.Formatter('%(asctime)-15s %(levelname)-8s %(message)s')

    logFile = 'Account Creation.log'

    h1 = RotatingFileHandler(filename=logFile, mode='a', maxBytes=20 * 1024 * 1024, backupCount=2)
    h1.setFormatter(log_formatter)
    h1.setLevel(logging.DEBUG)

    h2 = logging.StreamHandler(sys.stdout)
    h2.setLevel(logging.INFO)
    h2.setFormatter(logging.Formatter('%(message)s'))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    root.addHandler(h1)
    root.addHandler(h2)

    create_user()

    for handler in root.handlers:
        handler.close()
        root.removeFilter(handler)
