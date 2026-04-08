CREATE TABLE "user" (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL
);

CREATE TABLE post (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title   TEXT NOT NULL,
    user_id UUID REFERENCES "user"(id)
);
