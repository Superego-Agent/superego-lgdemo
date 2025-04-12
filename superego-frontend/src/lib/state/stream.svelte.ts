
let streamStore = $state({
  cache: {} as Record<string, ThreadCacheData>
});

// Export the state object directly for components to read
// Mutation functions and derived state will be added later
export { streamStore };