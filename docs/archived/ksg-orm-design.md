# Knowshowgo ORM Design

**Date**: 2025-01-07  
**Purpose**: Prototype-based object hydration (JavaScript-style ORM)

## Overview

The Knowshowgo ORM provides automatic object hydration that works like JavaScript prototype-based OOP. When querying for a KSG object (concept), it automatically:

1. Loads the concept (Topic with `isPrototype=false`)
2. Finds its prototype (via `instanceOf` association)
3. Loads prototype property definitions (PropertyDefs)
4. Merges prototype properties (schema) with concept values
5. Returns a hydrated object with all properties populated

## JavaScript Prototype Analogy

In JavaScript:
```javascript
// Prototype defines schema
function Person(name, email) {
  this.name = name;
  this.email = email;
}
Person.prototype.phone = null;  // Property defined in prototype

// Instance provides values
const john = new Person("John", "john@example.com");
// john automatically has: name, email, phone (from prototype)
```

In Knowshowgo ORM:
```python
# Prototype defines properties (PropertyDefs)
# Concept provides values
concept = ksg.get_concept_hydrated(concept_uuid)
# concept automatically has all prototype properties + concept values
```

## API Design

### `KSGORM` Class

```python
class KSGORM:
    def get_concept(self, concept_uuid: str, hydrate: bool = True) -> Optional[Dict[str, Any]]:
        """Get a concept and optionally hydrate it with prototype properties."""
        
    def hydrate_concept(self, concept_node: Node) -> Dict[str, Any]:
        """Hydrate a concept with its prototype properties."""
        
    def query(self, query_text: str, top_k: int = 5, hydrate: bool = True) -> List[Dict[str, Any]]:
        """Query concepts and optionally hydrate them."""
```

### `KnowShowGoAPI` Integration

```python
# Read operations
ksg.get_concept_hydrated(concept_uuid)  # Returns hydrated object
ksg.search_concepts(query, top_k=5, hydrate=True)  # Returns hydrated objects

# Write operations
ksg.create_object(prototype_name, properties)  # Create new object
ksg.save_object(hydrated_obj)  # Save object changes
ksg.update_properties(concept_uuid, properties)  # Update specific properties
```

## Hydration Process

1. **Load Concept**: Get the concept node (Topic with `isPrototype=false`)

2. **Find Prototype**: 
   - Search for `instanceOf` association edge
   - Or use `prototype_uuid` from concept props (backward compat)

3. **Load Prototype Properties**:
   - Find PropertyDefs via `defines_prop` edges (Prototype → PropertyDef)
   - Or search all PropertyDefs (fallback)

4. **Merge Properties**:
   - Start with concept values (instance data)
   - Add prototype properties (schema) that aren't in concept
   - Concept values override prototype defaults

5. **Inheritance**:
   - If prototype has parent (via `inherits` edge), load parent properties too
   - Parent properties are added if not already present

## Example Usage

### Read Operations

```python
from src.personal_assistant.knowshowgo import KnowShowGoAPI

# Create API
ksg = KnowShowGoAPI(memory, embed_fn=embed_fn)

# Query with hydration (ORM-style)
hydrated = ksg.get_concept_hydrated(procedure_uuid)
# hydrated now has:
# - All concept values (name, description, steps)
# - All prototype properties (from Procedure prototype)
# - All inherited properties (from parent prototypes)

# Search with hydration
results = ksg.search_concepts("login procedure", top_k=5, hydrate=True)
# All results are hydrated with prototype properties
```

### Write Operations

```python
# Create a new object from prototype (like JavaScript: new Person({...}))
obj = ksg.create_object(
    prototype_name="Procedure",
    properties={
        "name": "Login to X.com",
        "description": "Procedure to log into X.com",
        "steps": [{"tool": "web.get", "url": "https://x.com"}],
    },
)
# Returns hydrated object with UUID

# Modify object properties
obj["props"]["description"] = "Updated description"
obj["props"]["status"] = "completed"

# Save object back to knowledge graph
saved = ksg.save_object(obj)
# Returns updated hydrated object

# Update specific properties (like JavaScript: object.property = value)
updated = ksg.update_properties(
    concept_uuid=obj["uuid"],
    properties={
        "description": "New description",
        "priority": 5,
    },
)
# Returns updated hydrated object

# Complete workflow: create, modify, save
obj = ksg.create_object("Procedure", {"name": "Test", "description": "Initial"})
obj["props"]["description"] = "Modified"
saved = ksg.save_object(obj)
reloaded = ksg.get_concept_hydrated(saved["uuid"])  # Verify persistence
```

## Implementation Notes

### PropertyDef Lookup

Currently, PropertyDefs are loaded via:
1. `defines_prop` edges (if they exist) - Prototype → PropertyDef
2. Fallback: search all PropertyDefs (less efficient)

**Future Enhancement**: In production, prototypes should explicitly define properties via `defines_prop` edges.

### Inheritance Chain

The ORM supports prototype inheritance:
- Loads parent prototype properties
- Merges with child prototype properties
- Concept values override all prototype defaults

### Performance

- Hydration adds overhead (edge traversal, PropertyDef lookup)
- Use `hydrate=False` for raw data access
- Consider caching hydrated objects for frequently accessed concepts

## JavaScript Translation

This design is intended to translate to JavaScript:

```javascript
// JavaScript equivalent
class KSGORM {
  async getConcept(conceptUuid, hydrate = true) {
    const concept = await this.memory.get(conceptUuid);
    if (!hydrate) return concept;
    
    const prototype = await this.findPrototype(concept);
    const properties = await this.loadPrototypeProperties(prototype);
    
    return {
      ...concept.props,  // Concept values
      ...properties,      // Prototype properties
    };
  }
  
  async createObject(prototypeName, properties) {
    const prototype = await this.findPrototypeByName(prototypeName);
    const concept = await this.memory.create({
      prototype_uuid: prototype.uuid,
      ...properties,
    });
    return this.hydrateConcept(concept);
  }
  
  async saveObject(hydratedObj) {
    const concept = await this.memory.get(hydratedObj.uuid);
    concept.props = { ...concept.props, ...hydratedObj.props };
    await this.memory.save(concept);
    return this.hydrateConcept(concept);
  }
  
  async updateProperties(conceptUuid, properties) {
    const obj = await this.getConcept(conceptUuid, hydrate: true);
    obj.props = { ...obj.props, ...properties };
    return this.saveObject(obj);
  }
}
```

## Future Enhancements

1. **Lazy Loading**: Load properties on-demand
2. **Caching**: Cache hydrated objects
3. **Property Validation**: Validate concept values against PropertyDef constraints
4. **Type Coercion**: Convert values based on PropertyDef `valueType`
5. **Nested Hydration**: Hydrate related concepts (e.g., Procedure.steps)

