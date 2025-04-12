
let streamStore = $state({
  cache: {} as Record<string, ThreadCacheData>
});

// Export the state object directly for components to read
export { streamStore };