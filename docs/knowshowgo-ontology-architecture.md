# KnowShowGo Ontology Architecture

## Core Philosophy

KnowShowGo implements a **prototype-based OOP model** (JavaScript-style) where:
- **Prototypes** = Schemas/templates (type definitions, immutable, versioned)
- **Concepts** = Instances (actual data nodes following prototype schemas)
- **Concepts** are "neural/fuzzy" - have embeddings for similarity matching
- **Prototypes** are "symbolic" - schemas that define structure
- All prototypes derive from a root **ObjectPrototype**
- Prototypes are **immutable but versioned**
- Data flows as JSON objects (no hard typing, matching CPMS JavaScript approach)

**Key Principle**: Prototypes are the schemas/templates. Concepts are the actual instances/data nodes added to KnowShowGo.

## Ontology Structure

### Root Schema
- **Concept** - Root prototype for all nodes in KnowShowGo
- **ObjectPrototype** - Root prototype for all prototype definitions

### Prototype Hierarchy
```
ObjectPrototype (root, immutable, versioned)
  ├─ Concept (root for all concept nodes)
  │   ├─ Proposition (RDF-style subject-predicate-object triples)
  │   │   ├─ PropositionSubject
  │   │   ├─ PropositionPredicate
  │   │   └─ PropositionObject
  │   ├─ Task
  │   ├─ Procedure
  │   ├─ DAG
  │   ├─ CalendarEvent
  │   ├─ Person
  │   └─ ... (other prototypes as needed)
```

### Proposition Storage (RDF-style Triples)

Propositions store knowledge as **subject-predicate-object** triples:

```
Proposition Concept:
  - subject_uuid: UUID of subject concept
  - predicate_uuid: UUID of predicate (verb/action) concept
  - object_uuid: UUID of object concept
  - All parts reference nested concepts in KnowShowGo
```

Example:
- "John logged into X.com"
- Subject: Person("John")
- Predicate: Action("logged into")
- Object: Website("X.com")
- Stored as Proposition linking these three concepts

## Memory Architecture

### Conversation History
- ALL conversation entries (user + LLM) stored with embeddings
- Separate vector embedding table for history
- Eventually stored in KnowShowGo/Arango
- Enables semantic search over conversation history

### Topic Extraction & Context Retrieval
1. **LLM extracts topics** from user input (if not already prompted)
2. **Query KnowShowGo by embedding** for extracted topics
3. **Add retrieved context** to LLM completion context
4. **Add new things** the system doesn't know about

### Semantic Memory Flow
```
User Input
  ↓
Extract Topics (LLM)
  ↓
Query KnowShowGo by Embedding (topics)
  ↓
Retrieve Relevant Concepts/Propositions
  ↓
Add to LLM Context
  ↓
LLM Completion
  ↓
Store New Concepts/Propositions
```

## Pre-seeded Prototypes (Minimal Set)

Only essential prototypes for personal assistant with online learning semantic memory:

1. **Task** - User tasks/to-dos
2. **Procedure** - Learned procedures/steps
3. **DAG** - Directed acyclic graphs (for procedures with dependencies)
4. **CalendarEvent** - Calendar entries
5. **Person** - People/contacts
6. **Concept** (root) - Base for all concepts
7. **ObjectPrototype** (root) - Base for all prototypes
8. **Proposition** - RDF-style triples (subject-predicate-object)
9. **PropositionSubject** - Subject part of proposition
10. **PropositionPredicate** - Predicate/verb part of proposition
11. **PropositionObject** - Object part of proposition

**Note**: Keep minimal - only add prototypes as needed for functionality.

## Implementation Notes

### Prototype Creation
- Prototypes created via `ksg.create_prototype()` if missing
- All derive from ObjectPrototype
- Immutable but versioned (new version creates new prototype UUID)

### Concept Creation
- All concepts use "Concept" as base prototype (or derived prototypes)
- Concepts have embeddings for fuzzy matching
- Concepts can reference other concepts via UUIDs (for propositions)

### Proposition Storage
- Use `ksg.create_concept()` with Proposition prototype
- Store subject_uuid, predicate_uuid, object_uuid in props
- Link to nested concepts via edges or UUID references

### Conversation History
- Store each conversation entry as Concept with embedding
- Link to user/context concepts
- Enable semantic search over history

## Relationship to CPMS

- **CPMS** (JavaScript/JSON) matches this prototype-based OOP model
- **No hard typing** - JSON objects flow through system
- **Pattern matching** uses CPMS for symbolic matching
- **Embeddings** used for fuzzy/neural matching in KnowShowGo

## Python Prototyping Note

- This project is Python for **prototyping only**
- Production/system will use JavaScript/JSON model
- Keep Python code aligned with JavaScript prototype-based OOP principles
- Don't add hard typing that conflicts with prototype model

