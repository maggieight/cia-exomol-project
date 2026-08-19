# CIA Data Pipeline and ExoMol Website
This repository contains two related components developed for working with collision-induced absorption (CIA) database:

1. A Python pipeline for processing, standardizing, validating and generating the CIA dataset.
2. A Django-based ExoMol website for accessing and presenting the processed data.

## Input data
Input datasets are stored under: pipeline/input/
The following file is not included in this repository because it exceeds GitHub's 100 MB file-size limit:
pipeline/input/main/H2-He_2011.cia.txt
Before running processing steps that require this dataset, obtain the file from https://hitran.org/cia/.

<img width="599" height="31" alt="截屏2026-08-20 00 02 13" src="https://github.com/user-attachments/assets/5f47a620-9bcc-42bb-87d6-be9ed56b2abc" />

And place it at the path shown above.


## Local configuration
Local deployment settings, database credentials, secret keys, and other sensitive values are not stored in this repository.
If required, create: website/exomol3/local_settings.py 
Use the appropriate settings for the local development environment.
