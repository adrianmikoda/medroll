# Anonymization Pipeline (Athena HPC)
This document outlines the workflow for sanitizing sensitive medical data using our dedicated processing pipeline. We utilize the high-performance computing resources at [Cyfronet AGH](https://www.cyfronet.pl/pl) via [PLGrid](https://plgrid.pl/).

 ### Prerequisites
- PLGrid Account: Active account with granted access to the ATHENA cluster.
- VPN/SSH: Access to the Cyfronet infrastructure.
- Hugging Face Access:
    - Accepted Model License: You must visit the Llama-3.3-70B-Instruct model page and accept the license terms.
    - Access Token: A valid HF_TOKEN must be generated in your Hugging Face settings and set as an environment variable on the cluster to allow model download:
    ```bash
        export HF_TOKEN="your_hf_token_here"
    ```

### Upload scripts to the remote server
You can use the [script example](examples_scripts/upload_script_example.md) to upload the medroll service.

Example:
```bash
./upload_script_example.sh ~/.ssh/<name-of-your-ssh-key> <your-plg-username>
```
After, the uploading step you should connect to the remote server using your SSH key.

### Submitting the Jobs
To run medroll anonymization you should submit the job by [run script](examples_scripts/run_script_example.md)

```bash
sbatch run_script_example.sh
```

Once the job is running on the cluster and you have verified that the service is active, you can interact with the API remotely.

Since the API is running on an internal cluster node, it is not directly accessible from your local machine.

```bash
ssh -L 8000:localhost:8000 -N -f <your-plg-username>@athena.cyfronet.pl
```

You can access the API by navigating to http://localhost:8000 in your browser.



