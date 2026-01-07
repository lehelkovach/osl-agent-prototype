# Knowshowgo v0.1 System Design (handoff)

## 0) Purpose
Knowshowgo is a community-curated semantic registry: canonical **Topics** (concepts) with UUIDs, **typed schemas** (Prototypes), and **weighted associations** (properties-as-edges). It is designed to support:
- Public semantic tagging (semantic web layer)
- Open ontology + community governance (revisions, voting, merging duplicates)
- AI/LLM grounding (UUID-based concept anchors, embeddings)
- Personal assistant / learning agent semantic memory (tasks, events, procedures, actions, triggers, queues)

Core principles:
- **Everything is a first-class citizen** (Topic, Prototype, PropertyDef, Association, Revision, Vote, Procedure, Step…)
- **Fuzzy/prototype-theory friendly** via edge weights and competing assertions
- **Versioned** edits (Git/Wiki hybrid): revisions + votes select preferred state
- **API-first** so third-party apps and AI can read/write/query the semantic layer


## 1) Terminology
- **Topic**: any semantic unit (entity, concept, page, skill, schema, action, proposition…). Has a UUID.
- **Prototype**: a Topic that defines a **type/category schema** (like JS prototypes/classes).
- **PropertyDef**: defines a property/association type (predicate) and its value constraints.
- **Association**: an **edge** from Topic → (Topic or Value) with attributes (`weight`, provenance, votes, revision, status).

Working names:
- Root type: **BasePrototype**
- Instance nodes: **Topic**
- Schema nodes: **Prototype** (a Topic where `isPrototype=true`)
- Predicates: **PropertyDef**
- Edge records: **Association** (in edge collection `assoc`)


## 2) Storage model (graph-first; no Postgres)
Recommended DB for MVP: **ArangoDB** (documents + graph + optional search).

### 2.1 Document collections
- `topics` — all Topics (including Prototypes)
- `property_defs` — predicate definitions
- `values` — literal wrapper nodes (so everything remains edge-based)
- `revisions` — change proposals / diffs
- `users`
- `namespaces` — optional multi-tenant separation (public/org/personal)
- `embeddings` — optional (or embed vectors in `topics`)

### 2.2 Edge collections
- `assoc` — Topic → Topic/Value (properties-as-edges)
- `inherits` — Prototype → Prototype (schema inheritance)
- `defines_prop` — Prototype → PropertyDef (schema declares predicate)
- `votes` — User → Revision
- `subscribes` — User → Topic
- `merges` — Topic → Topic (optional “merged into” pointer)


## 3) Core schemas (documents)

### 3.1 Topic (base record)
All semantic units are Topics (including Prototypes).

```json
{
  "_key": "uuid-or-shortid",
  "uuid": "UUIDv4",
  "kind": "topic",
  "isPrototype": false,
  "label": "Air Jordan 1",
  "aliases": ["AJ1", "Air Jordan I"],
  "summary": "A model of basketball shoe by Nike/Jordan Brand.",
  "status": "active",
  "namespace": "public",
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",
  "createdBy": "users/<id>",
  "externalRefs": [
    {"system":"wikipedia","url":"..."},
    {"system":"schema.org","id":"..."}
  ]
}
```

### 3.2 Prototype (special Topic)
A Prototype is a Topic with `isPrototype=true`.

```json
{
  "_key": "person-prototype",
  "uuid": "…",
  "kind": "topic",
  "isPrototype": true,
  "label": "Person",
  "summary": "A human individual.",
  "status": "active"
}
```

Inheritance is represented by `inherits` edges:
- `topics/Person -[inherits]-> topics/BasePrototype`
- `topics/Event -[inherits]-> topics/BasePrototype`
etc.

### 3.3 PropertyDef (predicate definition)
Defines what an association means and constraints about its values.

```json
{
  "_key": "birthDate",
  "uuid": "…",
  "name": "birthDate",
  "valueType": "date",
  "cardinality": "0..1",
  "allowedTargetPrototypes": [],
  "description": "Date of birth",
  "status": "active"
}
```

Supported `valueType` (v0.1):
- `string | number | boolean | date | url | json | topic_ref`

### 3.4 Value (literal wrapper node)
Literal values become nodes so all properties remain edges.

```json
{
  "_key": "val_123",
  "type": "date",
  "value": "1977-05-01"
}
```


## 4) Association model (properties-as-edges with attributes)
All properties are edges in `assoc`. The predicate is stored as a pointer to `PropertyDef` using `p`.

```json
{
  "_from": "topics/<subjectKey>",
  "_to": "topics/<objectKey> OR values/<valueKey>",
  "p": "property_defs/<propKey>",
  "w": 0.87,
  "confidence": 0.75,
  "status": "accepted",
  "provenance": {"type":"user","user":"users/<id>","sourceUrl":"..."},
  "revisionId": "revisions/<id>",
  "votesUp": 12,
  "votesDown": 2,
  "createdAt": "ISO-8601"
}
```

Edge attributes (recommended):
- `w` (weight) float 0..1  ✅ primary fuzzy association strength
- `confidence` float 0..1
- `status` `proposed|accepted|rejected|deprecated`
- `provenance` { user/system/url }
- `revisionId` (Revision ref)
- `votesUp`, `votesDown` (or `voteScore`)
- timestamps


## 5) Governance: Revisions + Votes (Git/Wiki hybrid)

### 5.1 Revision (document)
A Revision proposes a change to a Topic, PropertyDef, or Association.

```json
{
  "_key": "rev_456",
  "targetType": "topic|property_def|assoc",
  "targetId": "topics/<id> OR property_defs/<id> OR assoc/<edgeKey>",
  "op": "create|update|delete|merge",
  "patch": {...},
  "createdBy": "users/<id>",
  "createdAt": "ISO-8601",
  "state": "open|accepted|rejected",
  "score": 0
}
```

### 5.2 Vote (edge)
`votes` edge: `users/<u> -[votes {value:+1|-1, weight?, createdAt}]-> revisions/<r>`

Acceptance policy (v0.1 simple):
- if `score >= threshold` => accepted
- allow curator/mod override if needed


## 6) v0.1 predefined PropertyDefs (predicate catalog)

### 6.1 Ontology core
- `instanceOf` (Topic → Prototype)
- `broaderThan` / `narrowerThan`
- `relatedTo`
- `partOf` / `hasPart`
- `synonymOf` (soft equivalence)
- `sameAs` (strong equivalence/merge)
- `hasSource` (→ DigitalResource or URL Value)

### 6.2 Identity & external refs
- `alias` (string Value)
- `externalUrl` (url Value)
- `imageUrl` (url Value)
- `schemaOrgType` (url or string Value)
- `wikipediaUrl` (url Value)

### 6.3 Time + scheduling (assistant)
- `startTime`, `endTime`, `dueTime` (date/datetime Value)
- `priority` (number Value)
- `status` (string Value)

### 6.4 Procedural memory (assistant)
- `hasStep` (Procedure → Step)
- `nextStep` (Step → Step)
- `usesCommandlet` (Step → Commandlet)
- `params` (json Value)
- `trigger` (Procedure → Trigger)
- `successCriteria` (json/string Value)
- `appliesToSite` (Procedure → WebResource)
- `runsProcedure` (QueueItem → Procedure)
- `context` (json Value)


## 7) v0.1 Prototypes to seed

### 7.1 Root
- `BasePrototype` (root schema)

### 7.2 Public semantic registry (minimum useful set)
- `Topic` (implicit)
- `Person`
- `Organization`
- `Place`
- `Thing` (generic physical object)
- `DigitalResource` (URL-anchored resource)
- `CreativeWork` (article/post/video)
- `Software` (optional)

### 7.3 Assistant / learning agent (minimum useful set)
- `Event`
- `Task`
- `Project`
- `Commandlet`
- `Procedure`
- `Step`
- `Trigger`
- `QueueItem`
- `WebResource` (for site identity like linkedin.com)


## 8) Assistant-specific schema details (v0.1)

### Person
- `givenName` (string)
- `familyName` (string)
- `email` (string)
- `phone` (string)
- `worksFor` (→ Organization)
- `knows` (→ Person)

### Organization
- `officialName` (string)
- `website` (url)
- `locatedIn` (→ Place)

### Place
- `address` (string)
- `geo` (json {lat,lon})
- `locatedIn` (→ Place)

### Event
- `startTime` (datetime)
- `endTime` (datetime)
- `location` (→ Place)
- `attendee` (→ Person)
- `about` (→ Topic)

### Task
- `description` (string)
- `dueTime` (datetime)
- `priority` (number)
- `status` (todo|doing|done|blocked)
- `dependsOn` (→ Task)
- `assignedTo` (→ Person)

### Project
- `hasTask` (→ Task)
- `goal` (string)
- `status` (string)

### Commandlet (primitive IO op)
- `argSchema` (json)
- `returnsSchema` (json)
Examples: HTTP_GET, BROWSER_GOTO, SCREENSHOT, CLICK_AT, TYPE_TEXT, WAIT_FOR_SELECTOR, READ_DOM_TEXT, FIND_ON_SCREEN

### Procedure (learned workflow)
- `hasStep` (→ Step)
- `trigger` (→ Trigger)
- `successCriteria` (json/string)
- `appliesToSite` (→ WebResource)
- `embedding` (vector or ref)

### Step (sequence/DAG node)
- `order` (number)
- `usesCommandlet` (→ Commandlet)
- `params` (json)
- `expectation` (json/string)
- `nextStep` (→ Step)
- `onFail` (→ Step or Procedure)

### Trigger / Condition
- `triggerType` (time|event|condition)
- `cron` (string) optional
- `time` (datetime) optional
- `conditionExpr` (json) optional

Condition expression example:
```json
{
  "op": "AND|OR|NOT|EQ|CONTAINS|GT|LT",
  "args": [
    {"var":"inbox.unreadCount"},
    {"const": 0}
  ]
}
```

### QueueItem (priority queue / stack)
- `enqueuedAt` (datetime)
- `priority` (number)
- `state` (queued|running|done|failed)
- `runsProcedure` (→ Procedure)
- `context` (json)


## 9) Embeddings integration (v0.1 minimal)
Store embeddings for:
- Topics (semantic disambiguation)
- Procedures (retrieve learned skills)
- Optionally PropertyDefs (predicate semantics)

Implementation options:
- store vectors in `topics.embedding` / `topics.embeddingModel`
- or store in `embeddings` collection keyed by Topic UUID


## 10) API v0.1 (REST minimal)

### Read
- `GET /topics/search?q=...`
- `GET /topics/{uuid}`
- `GET /topics/{uuid}/associations` (group by predicate)
- `GET /topics/{uuid}/graph?depth=1&minWeight=0.2`
- `GET /resolve?q=...` (text → best UUID + candidates)

### Write
- `POST /topics`
- `POST /prototypes`
- `POST /property-defs`
- `POST /associations` (create assoc edge with `p` + `w` + provenance)

### Governance
- `POST /revisions`
- `POST /revisions/{id}/vote`
- `POST /topics/{uuid}/merge` (curated merge => sameAs)

### Assistant
- `POST /procedures`
- `POST /queue/enqueue`
- `GET /queue/next?workerId=...`
- `POST /queue/{itemId}/complete`


## 11) Build order (to ship)
1) DB setup: collections, edges, indexes
2) Topic CRUD + Prototype inheritance + PropertyDef CRUD
3) Association create/read with weights (this is the heart)
4) Search/resolve (label+aliases; then synonyms; then embeddings)
5) Seed assistant prototypes (Event/Task/Procedure/Commandlet/Step/Trigger/QueueItem)
6) Revisions + voting (simple threshold policy)
7) Subscriptions + notifications/webhooks (optional)


## 12) Seed data checklist (day-one)
Prototypes:
- BasePrototype, Person, Organization, Place, DigitalResource, CreativeWork, Thing
- Event, Task, Project
- Commandlet, Procedure, Step, Trigger, QueueItem, WebResource

PropertyDefs (minimum):
- instanceOf, alias, externalUrl, imageUrl, wikipediaUrl, schemaOrgType
- synonymOf, sameAs, relatedTo, broaderThan, narrowerThan, partOf, hasPart, hasSource
- startTime, endTime, dueTime, priority, status
- hasStep, nextStep, usesCommandlet, params, trigger, successCriteria, appliesToSite
- runsProcedure, context
