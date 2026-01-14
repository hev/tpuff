"""Turbopuffer region definitions.

Source: https://turbopuffer.com/docs/regions
"""

from typing import Literal

# All available Turbopuffer regions
TURBOPUFFER_REGIONS: list[str] = [
    # GCP Regions
    "gcp-us-central1",
    "gcp-us-west1",
    "gcp-us-east4",
    "gcp-northamerica-northeast2",
    "gcp-europe-west3",
    "gcp-asia-southeast1",
    "gcp-asia-northeast3",
    # AWS Regions
    "aws-ap-southeast-2",
    "aws-eu-central-1",
    "aws-eu-west-1",
    "aws-us-east-1",
    "aws-us-east-2",
    "aws-us-west-2",
    "aws-ap-south-1",
]

# Default region
DEFAULT_REGION = "aws-us-east-1"

# Type for region literal
TurbopufferRegion = Literal[
    "gcp-us-central1",
    "gcp-us-west1",
    "gcp-us-east4",
    "gcp-northamerica-northeast2",
    "gcp-europe-west3",
    "gcp-asia-southeast1",
    "gcp-asia-northeast3",
    "aws-ap-southeast-2",
    "aws-eu-central-1",
    "aws-eu-west-1",
    "aws-us-east-1",
    "aws-us-east-2",
    "aws-us-west-2",
    "aws-ap-south-1",
]


def is_valid_region(region: str) -> bool:
    """Check if a region is valid."""
    return region in TURBOPUFFER_REGIONS


def get_api_base_url(region: str) -> str:
    """Get the API base URL for a region."""
    return f"https://{region}.turbopuffer.com"
