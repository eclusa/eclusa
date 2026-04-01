'use strict';

const { describe, test } = require('node:test');
const assert = require('node:assert/strict');

const openapi = require('../eclusa/bin/lib/parsers/openapi.cjs');
const prisma = require('../eclusa/bin/lib/parsers/prisma.cjs');
const sqlDdl = require('../eclusa/bin/lib/parsers/sql-ddl.cjs');

describe('OpenAPI parser', () => {
  const SAMPLE_SPEC = JSON.stringify({
    openapi: '3.0.0',
    info: { title: 'Test API', version: '1.0' },
    paths: {
      '/users': {
        get: {
          operationId: 'listUsers',
          responses: {
            '200': {
              content: { 'application/json': { schema: { type: 'array', items: { $ref: '#/components/schemas/User' } } } },
            },
          },
        },
        post: {
          operationId: 'createUser',
          requestBody: {
            content: { 'application/json': { schema: { $ref: '#/components/schemas/CreateUserInput' } } },
          },
          responses: {
            '201': {
              content: { 'application/json': { schema: { $ref: '#/components/schemas/User' } } },
            },
          },
        },
      },
    },
    components: {
      schemas: {
        User: {
          type: 'object',
          required: ['id', 'email'],
          properties: {
            id: { type: 'string' },
            email: { type: 'string' },
            name: { type: 'string', nullable: true },
            created_at: { type: 'string', format: 'date-time' },
            role: { type: 'string', enum: ['admin', 'user'] },
            posts: { type: 'array', items: { $ref: '#/components/schemas/Post' } },
          },
        },
        Post: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            title: { type: 'string' },
            author: { $ref: '#/components/schemas/User' },
          },
        },
        CreateUserInput: {
          type: 'object',
          properties: {
            email: { type: 'string' },
            name: { type: 'string' },
          },
        },
      },
      securitySchemes: {
        bearer: { type: 'http', scheme: 'bearer' },
      },
    },
  });

  test('detects OpenAPI format', () => {
    assert.ok(openapi.canParse(SAMPLE_SPEC, 'api.json'));
    assert.ok(openapi.canParse('openapi: "3.0.0"', 'api.yaml'));
    assert.ok(!openapi.canParse('CREATE TABLE foo', 'schema.sql'));
  });

  test('extracts entities from schemas', () => {
    const ir = openapi.parse(SAMPLE_SPEC, 'test:api');
    assert.ok(ir.entities.User);
    assert.ok(ir.entities.Post);
    assert.ok(ir.entities.CreateUserInput);
  });

  test('extracts fields with correct types', () => {
    const ir = openapi.parse(SAMPLE_SPEC, 'test:api');
    assert.strictEqual(ir.entities.User.fields.id.type, 'string');
    assert.strictEqual(ir.entities.User.fields.id.constraint, 'required');
    assert.strictEqual(ir.entities.User.fields.name.constraint, 'nullable');
    assert.strictEqual(ir.entities.User.fields.created_at.type, 'timestamp');
  });

  test('extracts enums', () => {
    const ir = openapi.parse(SAMPLE_SPEC, 'test:api');
    assert.strictEqual(ir.entities.User.fields.role.type, 'enum');
    assert.deepStrictEqual(ir.entities.User.fields.role.values, ['admin', 'user']);
  });

  test('extracts relations', () => {
    const ir = openapi.parse(SAMPLE_SPEC, 'test:api');
    assert.ok(ir.entities.User.relations.posts);
    assert.strictEqual(ir.entities.User.relations.posts.target, 'Post');
    assert.strictEqual(ir.entities.User.relations.posts.cardinality, 'one_to_many');
    assert.ok(ir.entities.Post.relations.author);
    assert.strictEqual(ir.entities.Post.relations.author.target, 'User');
  });

  test('extracts operations', () => {
    const ir = openapi.parse(SAMPLE_SPEC, 'test:api');
    assert.ok(ir.operations.length >= 2);
    const listOp = ir.operations.find(o => o.name === 'listUsers');
    assert.ok(listOp);
    assert.strictEqual(listOp.method, 'GET');
    assert.strictEqual(listOp.path, '/users');
  });

  test('extracts auth', () => {
    const ir = openapi.parse(SAMPLE_SPEC, 'test:api');
    assert.ok(ir.auth);
    assert.strictEqual(ir.auth.model, 'bearer_token');
  });

  test('sets source metadata', () => {
    const ir = openapi.parse(SAMPLE_SPEC, 'test:api');
    assert.strictEqual(ir.source.origin, 'test:api');
    assert.strictEqual(ir.source.format, 'openapi');
    assert.strictEqual(ir.source.version, '1.0');
  });
});

describe('Prisma parser', () => {
  const SAMPLE_SCHEMA = `
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

enum Role {
  ADMIN
  USER
  MODERATOR
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String?
  role      Role     @default(USER)
  posts     Post[]
  createdAt DateTime @default(now())
}

model Post {
  id        String   @id @default(cuid())
  title     String
  content   String?
  published Boolean  @default(false)
  author    User     @relation(fields: [authorId], references: [id])
  authorId  String
}
`;

  test('detects Prisma format', () => {
    assert.ok(prisma.canParse(SAMPLE_SCHEMA, 'schema.prisma'));
    assert.ok(prisma.canParse(SAMPLE_SCHEMA, 'anything'));
    assert.ok(!prisma.canParse('CREATE TABLE foo', 'schema.sql'));
  });

  test('extracts models as entities', () => {
    const ir = prisma.parse(SAMPLE_SCHEMA, 'test:prisma');
    assert.ok(ir.entities.User);
    assert.ok(ir.entities.Post);
  });

  test('extracts fields with correct types', () => {
    const ir = prisma.parse(SAMPLE_SCHEMA, 'test:prisma');
    assert.strictEqual(ir.entities.User.fields.id.type, 'string');
    assert.ok(ir.entities.User.fields.id.constraint.includes('unique'));
    assert.strictEqual(ir.entities.User.fields.email.type, 'string');
    assert.ok(ir.entities.User.fields.email.constraint.includes('unique'));
    assert.ok(ir.entities.User.fields.name.constraint.includes('nullable'));
    assert.strictEqual(ir.entities.User.fields.createdAt.type, 'timestamp');
  });

  test('extracts enums', () => {
    const ir = prisma.parse(SAMPLE_SCHEMA, 'test:prisma');
    assert.ok(ir.entities.Role);
    assert.deepStrictEqual(ir.entities.Role.fields.value.values, ['ADMIN', 'USER', 'MODERATOR']);
  });

  test('extracts relations', () => {
    const ir = prisma.parse(SAMPLE_SCHEMA, 'test:prisma');
    assert.ok(ir.entities.User.relations.posts);
    assert.strictEqual(ir.entities.User.relations.posts.target, 'Post');
    assert.strictEqual(ir.entities.User.relations.posts.cardinality, 'one_to_many');
    assert.ok(ir.entities.Post.relations.author);
    assert.strictEqual(ir.entities.Post.relations.author.target, 'User');
    assert.strictEqual(ir.entities.Post.relations.author.cardinality, 'many_to_one');
  });
});

describe('SQL DDL parser', () => {
  const SAMPLE_DDL = `
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name TEXT,
  role VARCHAR(20) DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE posts (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  content TEXT,
  published BOOLEAN DEFAULT false,
  author_id INTEGER NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TYPE subscription_status AS ENUM ('active', 'past_due', 'canceled');
`;

  test('detects SQL DDL format', () => {
    assert.ok(sqlDdl.canParse(SAMPLE_DDL, 'schema.sql'));
    assert.ok(sqlDdl.canParse(SAMPLE_DDL, 'anything'));
    assert.ok(!sqlDdl.canParse('model User { }', 'schema.prisma'));
  });

  test('extracts tables as entities', () => {
    const ir = sqlDdl.parse(SAMPLE_DDL, 'test:sql');
    assert.ok(ir.entities.Users);
    assert.ok(ir.entities.Posts);
  });

  test('extracts columns with correct types', () => {
    const ir = sqlDdl.parse(SAMPLE_DDL, 'test:sql');
    assert.strictEqual(ir.entities.Users.fields.id.type, 'number');
    assert.strictEqual(ir.entities.Users.fields.email.type, 'string');
    assert.strictEqual(ir.entities.Users.fields.created_at.type, 'timestamp');
    assert.strictEqual(ir.entities.Posts.fields.published.type, 'boolean');
  });

  test('extracts constraints', () => {
    const ir = sqlDdl.parse(SAMPLE_DDL, 'test:sql');
    assert.ok(ir.entities.Users.fields.email.constraint.includes('unique'));
    assert.ok(ir.entities.Users.fields.name.constraint.includes('nullable'));
  });

  test('extracts foreign key relations', () => {
    const ir = sqlDdl.parse(SAMPLE_DDL, 'test:sql');
    assert.ok(ir.entities.Posts.relations.author);
    assert.strictEqual(ir.entities.Posts.relations.author.target, 'Users');
    assert.strictEqual(ir.entities.Posts.relations.author.cardinality, 'many_to_one');
  });

  test('extracts PostgreSQL enums', () => {
    const ir = sqlDdl.parse(SAMPLE_DDL, 'test:sql');
    assert.ok(ir.entities.SubscriptionStatus);
    assert.deepStrictEqual(ir.entities.SubscriptionStatus.fields.value.values, ['active', 'past_due', 'canceled']);
  });
});

describe('IR to Qdrant points', () => {
  const { irToPoints, validateIR, createIR, addEntity, addOperation, addAuth } = require('../eclusa/bin/lib/ir.cjs');

  test('creates points from entities', () => {
    const ir = createIR('test:ir', 'test', '1.0');
    addEntity(ir, 'User', {
      id: { type: 'string', constraint: 'unique' },
      email: { type: 'string' },
    });

    const points = irToPoints(ir);
    assert.ok(points.length >= 1);
    assert.strictEqual(points[0].payload.entry_type, 'entity');
    assert.strictEqual(points[0].payload.entity_name, 'User');
    assert.ok(Array.isArray(points[0].vector));
    assert.strictEqual(points[0].vector.length, 384);
  });

  test('creates points from operations', () => {
    const ir = createIR('test:ir', 'test', '1.0');
    addOperation(ir, { name: 'createUser', method: 'POST', path: '/users', output: 'User' });

    const points = irToPoints(ir);
    const opPoint = points.find(p => p.payload.entry_type === 'operation');
    assert.ok(opPoint);
    assert.strictEqual(opPoint.payload.operation.name, 'createUser');
  });

  test('creates points from auth', () => {
    const ir = createIR('test:ir', 'test', '1.0');
    addAuth(ir, 'bearer_token', ['read', 'write']);

    const points = irToPoints(ir);
    const authPoint = points.find(p => p.payload.entry_type === 'auth');
    assert.ok(authPoint);
    assert.strictEqual(authPoint.payload.auth.model, 'bearer_token');
  });

  test('validates IR', () => {
    const ir = createIR('test', 'test', '1.0');
    assert.deepStrictEqual(validateIR(ir), []);

    assert.ok(validateIR({}).length > 0);
    assert.ok(validateIR({ source: {} }).length > 0);
  });
});

describe('embedding', () => {
  const { embedFallback, embedSync, deterministicId } = require('../eclusa/bin/lib/qdrant.cjs');

  test('produces fixed-dimension vectors', () => {
    const v = embedSync('hello world');
    assert.strictEqual(v.length, 384);
  });

  test('produces normalized vectors', () => {
    const v = embedSync('test input');
    const norm = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
    assert.ok(Math.abs(norm - 1.0) < 0.01, `Expected unit vector, got norm ${norm}`);
  });

  test('similar texts produce similar vectors', () => {
    const v1 = embedFallback('user authentication login');
    const v2 = embedFallback('user auth login');
    const v3 = embedFallback('database migration schema');

    const sim12 = cosine(v1, v2);
    const sim13 = cosine(v1, v3);
    assert.ok(sim12 > sim13, `"user auth login" should be more similar to "user authentication login" than "database migration schema"`);
  });

  test('deterministic IDs are stable', () => {
    const id1 = deterministicId('source', 'name');
    const id2 = deterministicId('source', 'name');
    assert.strictEqual(id1, id2);
  });

  test('different inputs produce different IDs', () => {
    const id1 = deterministicId('source1', 'name');
    const id2 = deterministicId('source2', 'name');
    assert.notStrictEqual(id1, id2);
  });
});

function cosine(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}
