import csv
import io
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session
from langfuse import Langfuse

from app.api.deps import get_current_user_org, get_db
from app.core import logging
from app.models import UserOrganization, UserProjectOrg
from app.utils import APIResponse
from app.crud.credentials import get_provider_credential

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evaluation"])


@router.post("/evaluation/upload-dataset")
async def upload_dataset(
    dataset_name: str,
    file: UploadFile = File(...),
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """
    Upload a CSV dataset for evaluation.
    The CSV file should have two columns: input and expected_output.
    Only the first 30 rows will be processed.
    """
    if not file.filename.endswith(".csv"):
        return APIResponse.failure_response(error="Only CSV files are supported")

    # Get Langfuse credentials
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=_current_user.project_id,
    )
    if not langfuse_credentials:
        return APIResponse.failure_response(
            error="Langfuse credentials not configured for this organization."
        )

    # Initialize Langfuse client
    langfuse = Langfuse(
        public_key=langfuse_credentials["public_key"],
        secret_key=langfuse_credentials["secret_key"],
        host=langfuse_credentials["host"],
    )
    # langfuse = Langfuse(
    #     public_key="pk-lf-00d2d47a-86f0-4d8f-9d8b-ef24fc722731",
    #     secret_key="sk-lf-5a7caba5-9293-409d-b1ef-e4b3fef990b7",
    #     host="https://cloud.langfuse.com",
    # )

    try:
        # Read and validate CSV file
        contents = await file.read()
        logger.info(f"Read {len(contents)} bytes from file")

        # Decode contents and create CSV reader
        csv_content = contents.decode("utf-8")
        logger.info(f"CSV content preview: {csv_content[:200]}...")

        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)

        # Validate headers
        if not reader.fieldnames:
            return APIResponse.failure_response(
                error="CSV file is empty or has no headers"
            )

        logger.info(f"CSV headers found: {reader.fieldnames}")

        if not all(
            header in reader.fieldnames for header in ["input", "expected_output"]
        ):
            return APIResponse.failure_response(
                error="CSV must contain 'input' and 'expected_output' columns"
            )

        # Create dataset
        try:
            dataset = langfuse.create_dataset(name=dataset_name)
            logger.info(f"Created dataset with ID: {dataset.id}")
        except Exception as e:
            logger.error(f"Error creating dataset: {str(e)}")
            return APIResponse.failure_response(
                error=f"Failed to create dataset: {str(e)}"
            )

        # Process rows (limited to 30)
        rows_processed = 0
        rows_data = []  # Store rows for logging

        for row in reader:
            if rows_processed >= 30:
                break

            try:
                # Log the row data
                logger.info(f"Processing row {rows_processed + 1}: {row}")

                # Create dataset item
                item = langfuse.create_dataset_item(
                    dataset_name=dataset_name,
                    input=row["input"],
                    expected_output=row["expected_output"],
                )
                logger.info(f"Created dataset item with ID: {item.id}")

                rows_processed += 1
                rows_data.append(row)
            except Exception as e:
                logger.error(f"Error processing row {rows_processed + 1}: {str(e)}")
                continue

        if rows_processed == 0:
            return APIResponse.failure_response(
                error="No rows were successfully processed"
            )

        # Log summary
        logger.info(f"Successfully processed {rows_processed} rows")
        logger.info(f"Processed data: {rows_data}")

        return APIResponse.success_response(
            data={
                "message": f"Successfully uploaded {rows_processed} rows to dataset '{dataset_name}'",
                "rows_processed": rows_processed,
                "dataset_id": dataset.id if hasattr(dataset, "id") else None,
            }
        )

    except Exception as e:
        logger.error(f"Error uploading dataset: {str(e)}")
        return APIResponse.failure_response(error=str(e))
    finally:
        await file.close()
