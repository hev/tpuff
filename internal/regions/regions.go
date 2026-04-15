package regions

// All available Turbopuffer regions.
var TurbopufferRegions = []string{
	// GCP Regions
	"gcp-us-central1",
	"gcp-us-west1",
	"gcp-us-east4",
	"gcp-northamerica-northeast2",
	"gcp-europe-west3",
	"gcp-asia-southeast1",
	"gcp-asia-northeast3",
	// AWS Regions
	"aws-ap-southeast-2",
	"aws-eu-central-1",
	"aws-eu-west-1",
	"aws-us-east-1",
	"aws-us-east-2",
	"aws-us-west-2",
	"aws-ap-south-1",
}

// DefaultRegion is the default Turbopuffer region.
const DefaultRegion = "aws-us-east-1"

// IsValid checks if a region is valid.
func IsValid(region string) bool {
	for _, r := range TurbopufferRegions {
		if r == region {
			return true
		}
	}
	return false
}
