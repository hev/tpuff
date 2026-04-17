package schema

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"
)

// Valid simple schema types.
var ValidSimpleTypes = map[string]bool{
	"string": true,
	"uint64": true,
	"uuid":   true,
	"bool":   true,
}

// VectorTypePattern matches vector types like [1536]f32 or [768]f16.
var VectorTypePattern = regexp.MustCompile(`^\[\d+\]f(16|32)$`)

// Valid keys for complex type objects.
var ValidTypeKeys = map[string]bool{
	"type":             true,
	"full_text_search": true,
	"regex_index":      true,
	"filterable":       true,
}

// SchemaDiff holds the result of comparing two schemas.
type SchemaDiff struct {
	Unchanged map[string]string      // attr -> display type
	Additions map[string]string      // attr -> display type
	Conflicts map[string][2]string   // attr -> [old_type, new_type]
}

// HasConflicts returns true if there are any type conflicts.
func (d *SchemaDiff) HasConflicts() bool {
	return len(d.Conflicts) > 0
}

// HasChanges returns true if there are any additions or conflicts.
func (d *SchemaDiff) HasChanges() bool {
	return len(d.Additions) > 0 || len(d.Conflicts) > 0
}

// NormalizeSchemaType normalizes a schema type to a comparable string.
// Handles strings, map[string]any, and other types.
func NormalizeSchemaType(attrType any) string {
	switch v := attrType.(type) {
	case string:
		return v
	case map[string]any:
		b, _ := json.Marshal(v)
		return string(b)
	default:
		return fmt.Sprintf("%v", v)
	}
}

// SchemaTypeForDisplay converts a schema type to a human-readable string.
func SchemaTypeForDisplay(attrType any) string {
	switch v := attrType.(type) {
	case string:
		return v
	case map[string]any:
		if len(v) == 1 {
			if t, ok := v["type"]; ok {
				return fmt.Sprintf("%v", t)
			}
		}
		b, _ := json.Marshal(v)
		return string(b)
	default:
		return fmt.Sprintf("%v", v)
	}
}

// ValidateSchemaType validates a single schema attribute type.
// Returns a list of error messages (empty if valid).
func ValidateSchemaType(attrName string, attrType any) []string {
	var errors []string

	switch v := attrType.(type) {
	case string:
		if ValidSimpleTypes[v] {
			return nil
		}
		if VectorTypePattern.MatchString(v) {
			return nil
		}
		validTypes := sortedSimpleTypes()
		errors = append(errors, fmt.Sprintf(
			"Attribute '%s': invalid type '%s'. Valid types: %s, or vector format [dims]f32/f16",
			attrName, v, strings.Join(validTypes, ", ")))

	case map[string]any:
		typeVal, hasType := v["type"]
		if !hasType {
			errors = append(errors, fmt.Sprintf(
				"Attribute '%s': complex type object must have a 'type' key", attrName))
		} else {
			baseType, isStr := typeVal.(string)
			if !isStr {
				errors = append(errors, fmt.Sprintf(
					"Attribute '%s': 'type' must be a string", attrName))
			} else if !ValidSimpleTypes[baseType] && !VectorTypePattern.MatchString(baseType) {
				validTypes := sortedSimpleTypes()
				errors = append(errors, fmt.Sprintf(
					"Attribute '%s': invalid base type '%s'. Valid types: %s, or vector format [dims]f32/f16",
					attrName, baseType, strings.Join(validTypes, ", ")))
			}
		}

		// Check for unknown keys
		var unknownKeys []string
		for k := range v {
			if !ValidTypeKeys[k] {
				unknownKeys = append(unknownKeys, k)
			}
		}
		if len(unknownKeys) > 0 {
			sort.Strings(unknownKeys)
			validKeys := sortedValidTypeKeys()
			errors = append(errors, fmt.Sprintf(
				"Attribute '%s': unknown keys %v. Valid keys: %s",
				attrName, unknownKeys, strings.Join(validKeys, ", ")))
		}

		// Validate specific option types
		if fts, ok := v["full_text_search"]; ok {
			if _, isBool := fts.(bool); !isBool {
				errors = append(errors, fmt.Sprintf(
					"Attribute '%s': 'full_text_search' must be a boolean", attrName))
			}
		}
		if ri, ok := v["regex_index"]; ok {
			if _, isBool := ri.(bool); !isBool {
				errors = append(errors, fmt.Sprintf(
					"Attribute '%s': 'regex_index' must be a boolean", attrName))
			}
		}
		if f, ok := v["filterable"]; ok {
			if _, isBool := f.(bool); !isBool {
				errors = append(errors, fmt.Sprintf(
					"Attribute '%s': 'filterable' must be a boolean", attrName))
			}
		}

	default:
		errors = append(errors, fmt.Sprintf(
			"Attribute '%s': type must be a string or object, got %T", attrName, attrType))
	}

	return errors
}

// ValidateSchema validates a complete schema dictionary.
// Returns a list of error messages (empty if valid).
func ValidateSchema(schemaData map[string]any) []string {
	var errors []string

	for attrName, attrType := range schemaData {
		if attrName == "" {
			errors = append(errors, "Attribute name cannot be empty")
			continue
		}
		errors = append(errors, ValidateSchemaType(attrName, attrType)...)
	}

	return errors
}

// ComputeSchemaDiff computes the difference between current and new schemas.
// currentSchema can be nil (namespace doesn't exist yet).
func ComputeSchemaDiff(currentSchema, newSchema map[string]any) SchemaDiff {
	diff := SchemaDiff{
		Unchanged: make(map[string]string),
		Additions: make(map[string]string),
		Conflicts: make(map[string][2]string),
	}

	if currentSchema == nil {
		currentSchema = map[string]any{}
	}

	// Normalize current schema
	currentNormalized := make(map[string]string)
	for attr, attrType := range currentSchema {
		currentNormalized[attr] = NormalizeSchemaType(attrType)
	}

	// Compare each attribute in new schema
	for attr, newType := range newSchema {
		newTypeNormalized := NormalizeSchemaType(newType)
		newTypeDisplay := SchemaTypeForDisplay(newType)

		oldNorm, exists := currentNormalized[attr]
		if !exists {
			diff.Additions[attr] = newTypeDisplay
		} else if oldNorm == newTypeNormalized {
			diff.Unchanged[attr] = newTypeDisplay
		} else {
			oldTypeDisplay := SchemaTypeForDisplay(currentSchema[attr])
			diff.Conflicts[attr] = [2]string{oldTypeDisplay, newTypeDisplay}
		}
	}

	return diff
}

// LoadSchemaFile loads and validates a schema from a JSON file.
func LoadSchemaFile(filePath string) (map[string]any, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("Schema file not found: %s", filePath)
		}
		return nil, fmt.Errorf("Error reading schema file: %w", err)
	}

	var raw any
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("Invalid JSON in schema file: %s", err)
	}

	schemaData, ok := raw.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("Schema file must contain a JSON object")
	}

	errors := ValidateSchema(schemaData)
	if len(errors) > 0 {
		return nil, fmt.Errorf("Invalid schema:\n  %s", strings.Join(errors, "\n  "))
	}

	return schemaData, nil
}

func sortedSimpleTypes() []string {
	types := make([]string, 0, len(ValidSimpleTypes))
	for t := range ValidSimpleTypes {
		types = append(types, t)
	}
	sort.Strings(types)
	return types
}

func sortedValidTypeKeys() []string {
	keys := make([]string, 0, len(ValidTypeKeys))
	for k := range ValidTypeKeys {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
