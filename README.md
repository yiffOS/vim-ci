# vim-ci

Python script to automatically update Vim because it's releases are terrible.

To run, create a file called `.env` in the same directory based on `template.env`. You'll need an SMTP server to send emails, a GitHub token to poll Vim's repo, a GPG private key, git user details, and finally a git repo to do the automation in.