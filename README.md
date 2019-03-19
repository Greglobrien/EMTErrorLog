# EMTErrorLog
A tool for pulling logs from Elemental MediaTailor around the Error so you don't need to

This tool assumes a few things in order to work: 
- the first is that you're already using AWS MediaTailor 
- you're logging the output of Ads served to the `MediaTailor/AdDecisionServerInteractions` 

Next, this tool is designed to be run via SAM CLI, it accesses your AWS CLI credentials as well 
- _still working on the IAM Policy and roles_

Next `pip install -r requirements.txt --target .` 
install the requirements into a subfolder called `requirements` create a folder in 
S3 and make sure your credentials have R/W access to it.  

Then you can run a test using:

`sam local invoke EMTErrorLog --event event.json`

You can then deploy this tool into production in AWS nearly as easily

`sam package --template-file template.yml --s3-bucket S3_BUCKET_NAME --output-template-file packaged.yml`

`sam deploy --template-file packaged.yml --stack-name <STACK NAME> --capabilities CAPABILITY_IAM`