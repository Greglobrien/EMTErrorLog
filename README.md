# EMTErrorLog
A tool for pulling logs from Elemental MediaTailor around the Error so you don't need to

This tool is designed to be run and deployed via SAM CLI - _still working on the IAM Policy and roles_

after pip installing the requirements into a subfolder called `requirements` you can run a test using:

`sam local invoke EMTErrorLog --event event.json`