# SRSDAccountCreation
Creates users for Snake River School District. Deletes old users and creates accounts for upcoming 2nd graders

1. [Get the latest version of Python 3.](https://www.python.org/downloads)
2. At the [main github page](https://github.com/benemortasia/SRSDAccountCreation), press the green "Clone or download" and download the ZIP.

3. Extract the ZIP in a memorable location, as you will be running the script from that folder.

4. Open a Command Prompt in the "SRSDAccountCreation-master" folder. An easy way to do this is to open that folder, Right Click while holding Shift, then click "Open command prompt here"
     * Newer versions of Windows will have PowerShell instead of command prompt. This also works. Just click on "Open PowerShell window here" instead.
     
5. To perform the one-time setup, run the following in the command prompt or PowerShell window:

  `python.exe setup.py develop`
  
6. Before running the script, make sure a valid SFTP account username and password are in the code. There are two instances: one in the usernames_from_sftp function, and one in the update_students_in_ps function.

7. If the jrbimprt utility is not located at C:\jrb\Part_4\jrbimprt.exe , then the file path needs to be changed in the import_using_jrb function.

8. Make sure you are logged into Open Enterprise Server because jrbimprt needs to know which LDAP server to create the accounts in.

9. Run the following anytime you want to use the script (you won't have to run the setup command in Step 5 anymore):

  `python.exe create_user.py`
