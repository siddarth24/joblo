import logging
import cloudconvert
import requests
import os # For os.path.exists, though it might be better to ensure file is readable before passing to client

logger = logging.getLogger(__name__)

class CloudConvertClient:
    def __init__(self, api_key: str, sandbox: bool = False):
        self.api_key = api_key
        self.sandbox = sandbox
        try:
            cloudconvert.configure(api_key=self.api_key, sandbox=self.sandbox)
            logger.info(f"CloudConvertClient configured. Sandbox: {self.sandbox}")
        except Exception as e:
            logger.error(f"Failed to configure CloudConvert in CloudConvertClient: {e}", exc_info=True)
            # Depending on the library, configuration might not raise an immediate error
            # but an error might occur on the first API call if config is bad.
            # For now, assume configure might raise or is a prerequisite.
            raise ConnectionError(f"CloudConvertClient configuration failed: {e}")

    def convert_md_to_docx(self, input_md_path: str, output_docx_path: str):
        """
        Converts a Markdown file to DOCX using CloudConvert.
        The input_md_path must exist and be readable.
        The output_docx_path is where the converted file will be saved.
        """
        logger.info(f"CloudConvertClient attempting to convert {input_md_path} to {output_docx_path}")

        if not os.path.exists(input_md_path):
            logger.error(f"Input Markdown file not found by CloudConvertClient: {input_md_path}")
            raise FileNotFoundError(f"Input Markdown file does not exist: {input_md_path}")

        try:
            job_payload = {
                "tasks": {
                    'import-my-file': {
                        'operation': 'import/upload'
                    },
                    'convert-my-file': {
                        'operation': 'convert',
                        'input': 'import-my-file',
                        'output_format': 'docx'
                    },
                    'export-my-file': {
                        'operation': 'export/url',
                        'input': 'convert-my-file'
                    }
                }
            }
            
            logger.debug("Creating CloudConvert job...")
            job = cloudconvert.Job.create(payload=job_payload)
            job_id = job.get('id', 'unknown_job_id')
            logger.info(f"CloudConvert job {job_id} created.")

            import_task = next((task for task in job.get("tasks", []) if task.get("name") == "import-my-file"), None)
            if not import_task or not import_task.get("result") or not import_task["result"].get("form"):
                logger.error(f"Import task or its result/form not found in CloudConvert job {job_id}. Job details: {job}")
                raise RuntimeError(f"Could not find import task details in CloudConvert job {job_id}.")

            upload_url = import_task["result"]["form"]["url"]
            upload_params = import_task["result"]["form"]["parameters"]

            logger.info(f"Uploading {input_md_path} to CloudConvert for job {job_id}...")
            with open(input_md_path, 'rb') as file:
                files = {'file': file}
                response = requests.post(upload_url, data=upload_params, files=files)
                response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
            logger.info(f"File {input_md_path} uploaded successfully for job {job_id}.")

            logger.info(f"Waiting for CloudConvert job {job_id} to complete...")
            job = cloudconvert.Job.wait(id=job_id) # Wait for job completion

            if job.get("status") != "finished":
                logger.error(f"CloudConvert job {job_id} did not finish successfully. Status: {job.get('status')}. Job: {job}")
                raise RuntimeError(f"CloudConvert job {job_id} failed. Status: {job.get('status')}")

            export_task = next((task for task in job.get("tasks", []) if task.get("name") == "export-my-file" and task.get("status") == "finished"), None)
            if not export_task or not export_task.get("result") or not export_task["result"].get("files"):
                logger.error(f"Export task not found or not finished, or no files in result for job {job_id}. Job: {job}")
                raise RuntimeError(f"Could not find successful export task details in CloudConvert job {job_id}.")

            file_info = export_task["result"]["files"][0]
            download_url = file_info["url"]

            logger.info(f"Downloading converted file from {download_url} for job {job_id}...")
            response = requests.get(download_url)
            response.raise_for_status()
            with open(output_docx_path, 'wb') as out_file:
                out_file.write(response.content)
            logger.info(f"File downloaded successfully from CloudConvert to: {output_docx_path} for job {job_id}")

        except requests.exceptions.RequestException as req_err:
            logger.error(f"HTTP request error during CloudConvertClient operation (job {job_id if 'job_id' in locals() else 'unknown'}): {req_err}", exc_info=True)
            raise ConnectionError(f"CloudConvert API request failed: {req_err}")
        except Exception as e:
            logger.error(f"Error during CloudConvertClient operation (job {job_id if 'job_id' in locals() else 'unknown'}): {e}", exc_info=True)
            # This could be an error from cloudconvert library itself, or unexpected structure
            raise RuntimeError(f"General error during CloudConvert conversion: {e}") 