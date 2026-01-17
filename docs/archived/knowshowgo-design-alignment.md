# Knowshowgo Design Alignment

**Date**: 2025-01-07  
**Status**: In Progress  
**Reference**: `docs/Knowshowgo_SYSTEM_DESIGN_v0.1.md`

## Overview

This document tracks the alignment of the current implementation with the Knowshowgo v0.1 system design. The design document uses "Topic" terminology, but we maintain "Concept" terminology in the codebase for backward compatibility.

## Key Design Principles

1. **Everything is a Topic**: All nodes (Prototypes, Concepts, PropertyDefs) are Topics
2. **Prototypes are Topics with `isPrototype=true`**: Schemas/templates are Topics marked as Prototypes
3. **Concepts are Topics with `isPrototype=false`**: Instance data nodes
4. **Properties-as-edges**: All properties are edges in `assoc` collection with PropertyDef reference (`p`)
5. **Fuzzy associations**: Edges have weight (`w`) 0.0-1.0 for fuzzy membership
6. **Versioned and governed**: Revisions + voting (future enhancement)

## Implementation Status

### ✅ Completed

1. **Node Model Alignment**
   - Updated `Node` model to support Knowshowgo Topic schema fields
   - Added support for `label`, `aliases`, `summary`, `isPrototype`, `status`, `namespace`
   - Maintains backward compatibility with existing `kind`, `labels`, `props`

2. **Edge Model Alignment**
   - Updated `Edge` model to support Knowshowgo Association fields
   - Added support for `p` (PropertyDef reference), `w` (weight), `confidence`, `status`, `provenance`
   - Maintains backward compatibility with `rel` field

3. **Prototype Seeding**
   - Updated seed data to match Knowshowgo v0.1 prototypes:
     - BasePrototype (root)
     - Person, Organization, Place, Thing, DigitalResource, CreativeWork
     - Event, Task, Project
     - Commandlet, Procedure, Step, Trigger, QueueItem, WebResource
   - Prototypes created as Topics with `isPrototype=true`
   - Inheritance edges use `inherits` relationship

4. **PropertyDef Seeding**
   - Updated to match Knowshowgo v0.1 catalog:
     - Ontology core: instanceOf, broaderThan, narrowerThan, relatedTo, partOf, hasPart, synonymOf, sameAs, hasSource
     - Identity & external refs: alias, externalUrl, imageUrl, schemaOrgType, wikipediaUrl
     - Time + scheduling: startTime, endTime, dueTime, priority, status
     - Procedural memory: hasStep, nextStep, usesCommandlet, params, trigger, successCriteria, appliesToSite, runsProcedure, context

5. **KnowShowGoAPI Updates**
   - `create_prototype()`: Creates Topics with `isPrototype=true`
   - `create_concept()`: Creates Topics with `isPrototype=false`, uses `instanceOf` association
   - `add_association()`: Supports PropertyDef reference (`p`) and weight (`w`)

### 🔄 In Progress / Future

1. **Value Nodes**: Literal values as wrapper nodes (deferred - not critical for agent functionality)
2. **Revisions + Voting**: Governance system (deferred - not critical for agent functionality)
3. **Namespace Support**: Multi-tenant separation (deferred - using "public" for now)
4. **External Refs**: Full support for externalRefs array (partially implemented)
5. **PropertyDef Lookup**: Enhanced PropertyDef lookup in associations (basic implementation done)

## Terminology Mapping

| Knowshowgo Design | Current Implementation | Notes |
|-------------------|------------------------|-------|
| Topic | Concept/Topic | Using "Concept" in code, but structure aligns with Topic |
| Prototype (isPrototype=true) | Prototype | Same |
| Concept (isPrototype=false) | Concept | Same |
| PropertyDef | PropertyDef | Same |
| Association (edge with p, w) | Edge (with p, w in props) | Same |
| inherits edge | inherits edge | Same |
| instanceOf | instanceOf | Same |

## Minimal Elements for Agent Functionality

Focusing on minimal elements needed for agent functionality:

1. ✅ **Prototypes**: BasePrototype, Procedure, Step, Task, Event, Person, Place
2. ✅ **PropertyDefs**: instanceOf, hasStep, nextStep, usesCommandlet, params, trigger, successCriteria
3. ✅ **Associations**: Support for PropertyDef references and weights
4. ✅ **Fuzzy matching**: Embedding-based similarity (already implemented)

## Backward Compatibility

All changes maintain backward compatibility:
- Existing code using `kind="Concept"` or `kind="Prototype"` still works
- `rel` field in edges still supported (alongside `p` PropertyDef reference)
- Existing property names (`name`, `description`) still work (alongside `label`, `summary`)

## Next Steps

1. Update tests to verify Knowshowgo design alignment
2. Add documentation for PropertyDef usage in associations
3. Consider Value nodes for literal values (if needed)
4. Enhance PropertyDef lookup in association creation

