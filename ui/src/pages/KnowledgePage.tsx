import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SearchBar } from '@/components/knowledge/SearchBar'
import { EntityRow } from '@/components/knowledge/EntityRow'
import { useCommunities, useEntitySearch } from '@/api/knowledge'

export function KnowledgePage() {
  const [tab, setTab] = useState('entities')
  const [query, setQuery] = useState('')
  const entitySearch = useEntitySearch(query)
  const { data: communities, isLoading: communitiesLoading, error: communitiesError } = useCommunities()

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Knowledge Graph</div>
        <h1 className="text-2xl font-semibold text-zinc-100">Knowledge Browser</h1>
      </header>

      <Tabs value={tab} onValueChange={setTab} className="space-y-6">
        <TabsList className="bg-zinc-900 p-1 text-zinc-500">
          <TabsTrigger value="entities">Entities</TabsTrigger>
          <TabsTrigger value="facts">Facts</TabsTrigger>
          <TabsTrigger value="communities">Communities</TabsTrigger>
        </TabsList>

        <TabsContent value="entities" className="space-y-4">
          <SearchBar onSearch={setQuery} />
          {!query.trim() ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 text-sm text-zinc-500">
              Enter a search term to explore entities
            </div>
          ) : entitySearch.isLoading ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 text-sm text-zinc-500">
              Searching entities...
            </div>
          ) : entitySearch.error ? (
            <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">
              Failed to load entities
            </div>
          ) : (entitySearch.data ?? []).length > 0 ? (
            <div className="space-y-3">
              {(entitySearch.data ?? []).map((entity) => (
                <EntityRow key={entity.id} entity={entity} />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 text-sm text-zinc-500">
              No entities matched your search.
            </div>
          )}
        </TabsContent>

        <TabsContent value="facts" className="space-y-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 text-sm text-zinc-500">
            Facts are shown inline when an entity is expanded.
          </div>
        </TabsContent>

        <TabsContent value="communities" className="space-y-4">
          {communitiesLoading ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 text-sm text-zinc-500">
              Loading communities...
            </div>
          ) : communitiesError ? (
            <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">
              Failed to load communities
            </div>
          ) : (communities ?? []).length > 0 ? (
            <div className="space-y-3">
              {(communities ?? []).map((community) => (
                <div key={community.id} className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3">
                  <div className="text-sm font-medium text-zinc-100">{community.name}</div>
                  <Badge variant="outline" className="border-zinc-800 bg-zinc-900 text-zinc-300">
                    {community.member_count} members
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 text-sm text-zinc-500">
              No communities available.
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
