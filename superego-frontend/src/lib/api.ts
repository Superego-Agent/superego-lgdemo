// src/lib/api.ts
import { messages, isLoading, globalError, currentThreadId, availableThreads, availableConstitutions } from './stores';
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { nanoid } from 'nanoid';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Helper for standard Fetch requests ---
async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> { isLoading.set(true); globalError.set(null); try { const response = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', ...options.headers, }, }); if (!response.ok) { let errorMsg = `HTTP error! Status: ${response.status}`; try { const errorBody = await response.json(); errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`; } catch (e) { /* Ignore */ } throw new Error(errorMsg); } if (!options.signal && !(options.headers && (options.headers as Record<string, string>)['Accept'] === 'text/event-stream')) { isLoading.set(false); } return await response.json() as T; } catch (error: any) { console.error('API Fetch Error:', error); globalError.set(error.message || 'An unknown API error occurred.'); if (!options.signal && !(options.headers && (options.headers as Record<string, string>)['Accept'] === 'text/event-stream')) { isLoading.set(false); } throw error; } }

// --- API Functions ---
export const fetchConstitutions = async (): Promise<ConstitutionItem[]> => { console.log('API: Fetching constitutions'); const constitutions = await apiFetch<ConstitutionItem[]>(`${BASE_URL}/constitutions`); availableConstitutions.set(constitutions); return constitutions; };
export const fetchThreads = async (): Promise<ThreadItem[]> => { console.log('API: Fetching threads'); const threads = await apiFetch<ThreadItem[]>(`${BASE_URL}/threads`); availableThreads.set(threads); return threads; };
export const fetchHistory = async (threadId: string): Promise<HistoryResponse> => { console.log(`API: Fetching history for ${threadId}`); try { const history = await apiFetch<HistoryResponse>(`${BASE_URL}/threads/${threadId}/history`); messages.set(history.messages || []); return history; } catch (error) { console.error(`Failed to fetch history for ${threadId}:`, error); messages.set([]); throw error; } };
export const createNewThread = async (): Promise<NewThreadResponse> => { console.log('API: Creating new thread'); const newThread = await apiFetch<NewThreadResponse>(`${BASE_URL}/threads`, { method: 'POST' }); currentThreadId.set(newThread.thread_id); messages.set([]); fetchThreads(); return newThread; };

// --- Real Streaming Functions ---
let streamController: AbortController | null = null;
export const cancelStream = () => { if (streamController) { console.log('API: Aborting active stream.'); streamController.abort(); streamController = null; if (get(isLoading)) { isLoading.set(false); } } };

// Helper to find the last AI message matching node/set
function findLastAiMessageIndex(msgs: MessageType[], nodeId: string | null, setId: string | null): number {
    return msgs.findLastIndex(msg => msg.sender === 'ai' && (msg.node ?? null) === nodeId && (!setId || (msg.set_id ?? null) === setId));
}

// SSE Message Handler - Simplified Tool Arg Appending (Sequence Based)
function handleSSEMessage(event: EventSourceMessage) {
    try {
        if (!event.data) { console.warn('SSE message received with no data.'); return; }
        const parsedData: SSEEventData = JSON.parse(event.data);
        const setId = parsedData.set_id;
        const nodeId = parsedData.node;

        messages.update(currentMsgs => {
            let updatedMsgs = [...currentMsgs];
            const lastMsgIndex = updatedMsgs.length - 1;

            switch (parsedData.type) {
                case 'chunk':
                    const chunkContent = parsedData.data as string;
                    if (chunkContent === null || chunkContent === undefined) break;
                    //@ts-ignore
                    const targetAiMsgIndexChunk = findLastAiMessageIndex(updatedMsgs, nodeId, setId);
                    let targetAiMsgChunk = targetAiMsgIndexChunk > -1 ? updatedMsgs[targetAiMsgIndexChunk] as AIMessage : null;
                    if (targetAiMsgChunk && typeof targetAiMsgChunk.content === 'string') {
                        updatedMsgs[targetAiMsgIndexChunk] = { ...targetAiMsgChunk, content: targetAiMsgChunk.content + chunkContent };
                    } else {
                        const newMsg: AIMessage = { id: nanoid(8), sender: 'ai', content: chunkContent, node: nodeId, set_id: setId, timestamp: Date.now(), tool_calls: [] }; // Init tool_calls
                        updatedMsgs.push(newMsg);
                    }
                    break;

                case 'ai_tool_chunk':
                    const toolChunkData = parsedData.data as SSEToolCallChunkData;
                                        //@ts-ignore
                    const targetAiMsgIndexTool = findLastAiMessageIndex(updatedMsgs, nodeId, setId);

                    if (targetAiMsgIndexTool > -1) {
                        let targetMsg = updatedMsgs[targetAiMsgIndexTool] as AIMessage;
                        if (!targetMsg.tool_calls) { targetMsg.tool_calls = []; } // Ensure array exists

                        // *** SIMPLIFIED LOGIC: Ignore ID, use sequence ***
                        if (toolChunkData.name) {
                            // If chunk has a name, assume it's the start of a NEW tool call
                            // Add it to the end of the array
                            targetMsg.tool_calls.push({
                                id: toolChunkData.id || nanoid(6), // Use ID if provided, else generate temp one
                                name: toolChunkData.name,
                                args: toolChunkData.args || "", // Start args string
                            });
                        } else if (toolChunkData.args !== undefined && targetMsg.tool_calls.length > 0) {
                            // If chunk only has args, append to the LAST tool call in the array
                            const lastCallIndex = targetMsg.tool_calls.length - 1;
                            targetMsg.tool_calls[lastCallIndex] = {
                                ...targetMsg.tool_calls[lastCallIndex], // Keep existing name/id
                                args: (targetMsg.tool_calls[lastCallIndex].args || "") + toolChunkData.args, // Append args
                            };
                        } else {
                            // Chunk has neither name nor args, or no previous tool call exists to append to. Ignore/Warn.
                             console.warn("Received ai_tool_chunk with no name or args, or no prior tool call to append to.", toolChunkData);
                        }
                        // Ensure reactivity for the message object
                        updatedMsgs[targetAiMsgIndexTool] = { ...targetMsg };

                    } else { console.warn("Received ai_tool_chunk but no matching AI message found.", parsedData); }
                    break;

                case 'tool_result':
                    const toolResultData = parsedData.data as SSEToolResultData;
                    const newToolResultMsg: ToolResultMessage = { id: nanoid(8), sender: 'tool_result', content: toolResultData.result, tool_name: toolResultData.tool_name, is_error: toolResultData.is_error, node: nodeId, set_id: setId, timestamp: Date.now(), tool_call_id: toolResultData.tool_call_id };
                    updatedMsgs.push(newToolResultMsg);
                    break;

                case 'error':
                    const errorMsg = parsedData.data as string;
                    console.error(`SSE Error Event (node: ${nodeId}, set: ${setId || 'N/A'}):`, errorMsg);
                    const newErrorMsg: SystemMessage = { id: nanoid(8), sender: 'system', content: `Error (node: ${nodeId || 'graph'}, set: ${setId || 'general'}): ${errorMsg}`, node: nodeId, set_id: setId, isError: true, timestamp: Date.now() };
                    updatedMsgs.push(newErrorMsg);
                    globalError.set(`Stream Error (set: ${setId || 'general'}): ${errorMsg}`);
                    break;

                case 'end':
                    const endData = parsedData.data as SSEEndData;
                    console.log(`SSE Stream ended (node: ${nodeId}, set: ${setId || 'N/A'}, thread: ${endData?.thread_id})`);
                    break;

                default:
                    console.warn('Unhandled SSE event type:', parsedData.type);
            }
            return updatedMsgs;
        });
    } catch (error) {
        console.error('Failed to parse SSE message data:', event.data, error);
        globalError.set(`Received malformed message from server: ${error instanceof Error ? error.message : String(error)}`);
    }
}

// --- Core Streaming Function (Common Logic) ---
async function performStreamRequest( endpoint: string, requestBody: StreamRunRequest | CompareRunRequest ): Promise<void> {
   console.log(`API: Connecting to ${endpoint}`); isLoading.set(true); globalError.set(null); cancelStream();
   const controller = new AbortController(); streamController = controller;
   try {
       await fetchEventSource(`${BASE_URL}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream', }, body: JSON.stringify(requestBody), signal: controller.signal, openWhenHidden: true,
           onopen: async (response) => { if (!response.ok) { let errorMsg = `SSE connection failed! Status: ${response.status}`; try { const errorBody = await response.json(); errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`; } catch (e) { /* Ignore */ } isLoading.set(false); streamController = null; throw new Error(errorMsg); } console.log(`SSE stream opened (${endpoint})`); },
           onmessage: (event) => { handleSSEMessage(event); },
           onclose: () => { console.log(`SSE stream closed (${endpoint}).`); if (streamController === controller) { isLoading.set(false); streamController = null; } const reqBody = requestBody as StreamRunRequest; if (endpoint === '/runs/stream' && reqBody.input && reqBody.thread_id === null && !controller.signal.aborted) { console.log("New thread stream finished, refreshing threads list."); fetchThreads(); } },
           onerror: (err) => { if (controller.signal.aborted) { console.log("Stream intentionally aborted."); return; } console.error(`SSE stream error (${endpoint}):`, err); isLoading.set(false); globalError.set(`Stream connection error: ${err.message || 'Unknown stream error'}`); if (streamController === controller) { streamController = null; } throw err; },
       });
   } catch (error) { if (!controller.signal.aborted) { console.error(`WorkspaceEventSource (${endpoint}) failed:`, error); if (get(isLoading)) { isLoading.set(false); } if (streamController === controller) { streamController = null; } if (!get(globalError)) { globalError.set(`Stream setup failed: ${error instanceof Error ? error.message : String(error)}`); } } else { console.log("Stream intentionally aborted (caught exception)."); if (get(isLoading)) { isLoading.set(false); } } }
}

// --- Specific Stream Run Functions ---
export const streamRun = async ( userInput: string, threadId: string | null, constitutionIds: string[] = ['none'] ): Promise<void> => { const requestBody: StreamRunRequest = { thread_id: threadId, input: { type: 'human', content: userInput }, constitution_ids: constitutionIds }; await performStreamRequest('/runs/stream', requestBody); };
export const streamCompareRun = async ( userInput: string, compareSetsConfig: CompareSet[] ): Promise<void> => { const requestBody: CompareRunRequest = { input: { type: 'human', content: userInput }, constitution_sets: compareSetsConfig.map(set => ({ id: set.id, constitution_ids: set.constitution_ids })) }; await performStreamRequest('/runs/compare/stream', requestBody); };