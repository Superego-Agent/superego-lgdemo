import { nanoid } from 'nanoid';
import { fetchConstitutionHierarchy } from '$lib/api/rest.svelte';

// --- Constants ---
const LOCAL_CONSTITUTIONS_KEY = 'superego_local_constitutions';

// --- Helper Function for Sorting UI Nodes ---
function sortNodes(a: UINode, b: UINode): number {
	if (a.type === 'folder' && b.type === 'file') return -1;
	if (a.type === 'file' && b.type === 'folder') return 1;

	// Both are folders or both are files, sort alphabetically
	const titleA = a.type === 'folder' ? a.title : a.metadata.title;
	const titleB = b.type === 'folder' ? b.title : b.metadata.title;
	return titleA.localeCompare(titleB);
}

// --- Helper Functions for Transforming Global Hierarchy ---
function transformGlobalFile(file: RemoteConstitutionMetadata): UIFileNode {
	return {
		type: 'file',
		metadata: file,
		uiPath: `remote:${file.relativePath}`
	};
}

function transformGlobalFolder(folder: ConstitutionFolder): UIFolderNode {
	const children: UINode[] = [
		...folder.subFolders.map(transformGlobalFolder), // Recursive call
		...folder.constitutions.map(transformGlobalFile)
	];
	children.sort(sortNodes); // Sort children within this folder 

	// Construct a unique-ish path for the folder node itself for keying/identification if needed
	// Using the first child's path prefix or just the title might be fragile.
	// Let's use a prefix and the title. The primary use is structure, children have the real paths.
	const folderUiPath = `remote:folder:${folder.folderTitle}`; // Simple identifier

	return {
		type: 'folder',
		title: folder.folderTitle,
		uiPath: folderUiPath,
		isExpanded: false, // Default to collapsed
		children: children
	};
}


// --- Main Store Class ---

export class ConstitutionStore {
	// --- Local Constitutions State ---
	localConstitutions: LocalConstitutionMetadata[] = $state([]);

	// --- Global Constitutions State ---
	globalHierarchy: ConstitutionHierarchy | null = $state(null);
	isLoadingGlobal: boolean = $state(false);
	globalError: string | null = $state(null);
	// Removed #hasFetchedGlobal guard

	constructor() {
		// --- Load initial state from localStorage ---
		if (typeof window !== 'undefined' && window.localStorage) {
			const stored = localStorage.getItem(LOCAL_CONSTITUTIONS_KEY);
			if (stored) {
				try {
					this.localConstitutions = JSON.parse(stored);
				} catch (e) {
					console.error("Failed to parse local constitutions from localStorage", e);
					localStorage.removeItem(LOCAL_CONSTITUTIONS_KEY); // Clear invalid data
					this.localConstitutions = [];
				}
			} else {
				this.localConstitutions = [];
			}
		} else {
			this.localConstitutions = [];
		}


		// --- Fetch Global Constitutions on Initialization ---
		this.#fetchGlobalData();
	}

	// --- Private Helper for Initial Fetch ---
	async #fetchGlobalData() {
		console.log('[ConstitutionStore] Initializing global constitution fetch...');
		this.isLoadingGlobal = true;
		this.globalError = null;
		try {
			const fetchedHierarchy = await fetchConstitutionHierarchy();
			this.globalHierarchy = fetchedHierarchy;
			console.log('[ConstitutionStore] Successfully fetched global constitution hierarchy.');
		} catch (err: any) {
			console.error("[ConstitutionStore] Failed to load global constitutions:", err);
			this.globalError = err.message || "Unknown error fetching global constitutions.";
		} finally {
			this.isLoadingGlobal = false;
		}
	}

	// --- Private Helper to Save Local State ---
	#saveLocalState() {
		// Check if running in a browser environment before accessing localStorage
		if (typeof window !== 'undefined' && window.localStorage) {
			localStorage.setItem(LOCAL_CONSTITUTIONS_KEY, JSON.stringify(this.localConstitutions));
			console.log('[ConstitutionStore] Saved local constitutions to localStorage.');
		}
	}

	// --- Methods for Local State Mutation ---

	/** Adds a new local constitution. */
	addItem(title: string, text: string): LocalConstitutionMetadata {
		const newConstitution: LocalConstitutionMetadata = {
			localStorageKey: nanoid(),
			title: title.trim(),
			text: text,
			source: 'local'
		};
		this.localConstitutions = [...this.localConstitutions, newConstitution];
		console.log(`[ConstitutionStore] Added local constitution: ${newConstitution.localStorageKey} (${newConstitution.title})`);
		this.#saveLocalState(); // Save after modification
		return newConstitution;
	}

	/** Updates an existing local constitution by its key. */
	updateItem(key: string, title: string, text: string): boolean {
		const index = this.localConstitutions.findIndex(c => c.localStorageKey === key);
		if (index !== -1) {
			const updatedConstitution = {
				...this.localConstitutions[index],
				title: title.trim(),
				text: text
			};
			const newList = [...this.localConstitutions];
			newList[index] = updatedConstitution;
			this.localConstitutions = newList;
			console.log(`[ConstitutionStore] Updated local constitution: ${key}`);
			this.#saveLocalState(); // Save after modification
			return true;
		}
		console.warn(`[ConstitutionStore] Attempted update on non-existent local constitution: ${key}`);
		return false;
	}

	/** Deletes a local constitution by its key. */
	deleteItem(key: string): boolean {
		const initialLength = this.localConstitutions.length;
		const filtered = this.localConstitutions.filter(c => c.localStorageKey !== key);
		if (filtered.length < initialLength) {
			this.localConstitutions = filtered; // Immutable update
			console.log(`[ConstitutionStore] Deleted local constitution: ${key}`);
			this.#saveLocalState(); // Save after modification
			return true;
		}
		console.warn(`[ConstitutionStore] Attempted delete on non-existent local constitution: ${key}`);
		return false;
	}

	// --- Derived State for UI Tree ---

	get displayTree(): UINode[] {
		// --- Handle Loading State ---
		if (this.isLoadingGlobal) {
			return [{
				type: 'folder',
				title: 'Loading Global...', // Use title property
				uiPath: 'loading:global',
				isExpanded: true,
				children: []
			}];
		}

		// --- Handle Error State ---
		if (this.globalError) {
			return [{
				type: 'folder',
				title: `Error Loading Global: ${this.globalError}`, // Use title property
				uiPath: 'error:global',
				isExpanded: true,
				children: []
			}];
		}

		// --- Transform Local Constitutions ---
		const localFiles: UIFileNode[] = this.localConstitutions.map(meta => {
			console.log("[ConstitutionStore] local constitution meta:", meta); 
			return {
				type: 'file',
				metadata: meta,
				uiPath: `local:${meta.localStorageKey}` 
			};
		});
		localFiles.sort(sortNodes); // Sort local files alphabetically by title

		const localFolder: UIFolderNode = {
			type: 'folder',
			title: 'Local', // Use title property
			uiPath: 'local:folder', // Identifier for the local folder itself
			isExpanded: true, // Default local folder to expanded
			children: localFiles
		};

		// --- Transform Global Constitutions ---
		let globalNodes: UINode[] = [];
		if (this.globalHierarchy) {
			const globalRootFolders = this.globalHierarchy.rootFolders.map(transformGlobalFolder);
			const globalRootFiles = this.globalHierarchy.rootConstitutions.map(transformGlobalFile);
			globalNodes = [...globalRootFolders, ...globalRootFiles];
			globalNodes.sort(sortNodes); // Sort root global folders (first) and files alphabetically
		}

		// --- Combine and Return ---
		const displayTree = [localFolder, ...globalNodes];
		console.log("[ConstitutionStore] displayTree:", displayTree);
		return displayTree;
	}
}

// --- Export Singleton Instance ---
export const constitutionStore = new ConstitutionStore();