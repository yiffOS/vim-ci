# Built in modules
import os
import urllib
import re
import shutil
import smtplib
from email import message
import datetime

# Pip modules
from github import Github
from dotenv import load_dotenv
from git import Repo
from gnupg import GPG

###############################################################################

### Setting up the environment
print("==> Setting up the environment...")

# Load the .env file
load_dotenv()

# Misc

date = datetime.datetime.today().strftime('%Y-%m-%d')

# SMTP Setup and Template

smtp_server = os.getenv('SMTP_SERVER')
smtp_port = os.getenv('SMTP_PORT')

sender = os.getenv('SENDER')
destination = os.getenv('DESTINATION')

smtp_username = os.getenv('SMTP_USERNAME')
smtp_password = os.getenv('SMTP_PASSWORD')

email_subtype = "plain"

email_subject = "yiffOS Vim update "

# Login to Github
g = Github(os.environ.get("GITHUB_TOKEN"))

# Import GPG key
gpg_key = GPG(gnupghome=os.path.expanduser("~/.gnupg"), verbose=False, use_agent=True)
gpg_import_result = gpg_key.import_keys(os.environ.get("GPG_KEY"))
assert gpg_import_result.fingerprints[0] == os.environ.get("GPG_FINGERPRINT"), "GPG key import failed, aborting."

gpg_key_id = os.environ.get("GPG_KEY_ID")

print("Cloning PKGSCRIPT repo...")
repo = Repo.init(os.path.join(os.getcwd(), "PKGSCRIPT"))

origin = repo.create_remote("origin", os.environ.get("REPO_URL"))
origin.fetch()

repo.create_head("main", origin.refs.main).set_tracking_branch(origin.refs.main).checkout()

# Set local git config with name and email
repo.config_writer().set_value("user", "name", os.environ.get("GIT_NAME")).release()
repo.config_writer().set_value("user", "email", os.environ.get("GIT_EMAIL")).release()

### Run Vim CI
print("==> Running Vim CI...")

print("Getting the latest tag...")
# Get the latest tag for vim
tag_version = g.get_repo("vim/vim").get_tags()[0].name
tag_tar = "https://github.com/vim/vim/archive/refs/tags/{}.tar.gz".format(tag_version)

# Download the tarball and calculate the sha512sum
print("Downloading vim tarball...")
urllib.request.urlretrieve(tag_tar, tag_version+ ".tar.gz")

print("Calculating sha512sum...")
sha512sum = os.popen('sha512sum ' + tag_version + '.tar.gz').read().split(' ')[0]

print("Modifying PKGSCRIPT...")
with open(os.path.join(os.getcwd(), "PKGSCRIPT/vim/PKGSCRIPT"), "r+") as f:
    pkgscript = f.read()
    pkgscript = re.sub("VERSION=\".+\"", "VERSION=\"" + tag_version[1:] + "\"", pkgscript)
    pkgscript = re.sub("SUM=\(\".+\"\)", "SUM=(\"" + sha512sum + "\")", pkgscript)
    f.seek(0)
    f.write(pkgscript)
    f.truncate()

print("Modifying PKGINFO...")
with open(os.path.join(os.getcwd(), "PKGSCRIPT/vim/PKGINFO"), "r+") as f:
    pkginfo = f.read()
    pkginfo = re.sub("    \"version\": \".+\",", "    \"version\": \"" + tag_version[1:] + "\",", pkginfo)
    f.seek(0)
    f.write(pkginfo)
    f.truncate()

## Create and push commit
print("==>Committing...")

print("Adding files...")
repo.index.add([os.path.join(os.getcwd(), "PKGSCRIPT/vim/PKGSCRIPT"), os.path.join(os.getcwd(), "PKGSCRIPT/vim/PKGINFO")])
repo.index.write()

print("Creating commit...")
repo.git.commit('-S', f'--gpg-sign={gpg_key_id}', '-m', f'Update Vim to {tag_version} (Automated)')
commit_id = repo.commit().hexsha

print("==> Pushing commit...")
origin.push().raise_if_error()

## Clean up
print("==> Cleaning up...")
os.remove(os.path.join(os.getcwd(), tag_version + ".tar.gz"))
shutil.rmtree(os.path.join(os.getcwd(), "PKGSCRIPT"))

###############################################################################

print("Sending email...")

email_content = """\
Vim has been updated to {} on {}!

Commit id: {}
GitLab link: {}
""".format(tag_version, date, commit_id, os.environ.get("COMMIT_WEB_URL") + commit_id)

try:
    msg = message.EmailMessage()
    msg.set_content(email_content)
    msg["Subject"] = email_subject + tag_version + " (" + date + ")"
    msg["From"] = sender

    conn = smtplib.SMTP(smtp_server, smtp_port)
    conn.set_debuglevel(False)
    conn.ehlo()
    conn.starttls()
    conn.login(smtp_username, smtp_password)

    try:
        conn.sendmail(sender, destination, msg.as_string())
    finally:
        conn.quit()

except smtplib.SMTPException as e:
    print("Error: unable to send email")
    print(e)