<script lang="ts">
	import Self from './ConstitutionNode.svelte';
	// Accept activeConfigModules prop
	const { node, level, isSelected: isSelectedProp, activeConfigModules, expandedFolderPaths, getModule, onToggleSelect, onShowDetail, onSliderInput, onToggleExpand } = $props<{
	  node: UINode;
	  level: number;
	  isSelected: boolean;
	  activeConfigModules: ConfiguredConstitutionModule[]; // Added prop
	  expandedFolderPaths: Set<string>;
	  getModule: (uiPath: string) => ConfiguredConstitutionModule | null;
	  onToggleSelect: (uiPath: string, isSelected: boolean, metadata: LocalConstitutionMetadata | RemoteConstitutionMetadata) => void;
	  onShowDetail: (metadata: LocalConstitutionMetadata | RemoteConstitutionMetadata) => void;
	  onSliderInput: (uiPath: string, level: number) => void;
	  onToggleExpand: (node: UIFolderNode) => void;
	}>();

	import IconFolderRegular from '~icons/fluent/folder-20-regular';
	import IconDocumentRegular from '~icons/fluent/document-20-regular';
	import IconChevronDown from '~icons/fluent/chevron-down-20-regular';
	import IconChevronRight from '~icons/fluent/chevron-right-20-regular';

	// Removed derived isSelected state, using isSelectedProp directly
	let module = $derived(node.type === 'file' && isSelectedProp ? getModule(node.uiPath) : null);

	 // Derive expanded state based on the prop from the parent
	 let isExpanded = $derived(node.type === 'folder' && expandedFolderPaths.has(node.uiPath));

</script>

<!-- === Component Template === -->
<div class="node-container" style="padding-left: {level * 1.5}rem;">

	<!-- === Folder Node === -->
	{#if node.type === 'folder'}
		<div class="node-content folder">
			<span class="chevron" onclick={() => onToggleExpand(node)} style="cursor: pointer;">
				{#if isExpanded}
				  <IconChevronDown />
				{:else}
				  <IconChevronRight />
				{/if}
			</span>
			<IconFolderRegular class="icon" />
			<!-- Removed selection count display -->
			<span class="title bold">{node.title}</span>
		</div>
		{#if isExpanded}
    {#each node.children as childNode (childNode.uiPath)}
      {@const childIsSelected = childNode.type === 'file' && activeConfigModules.some((m: ConfiguredConstitutionModule) => {
          if (childNode.metadata.source === 'remote' && 'relativePath' in m) {
              return m.relativePath === childNode.metadata.relativePath;
          } else if (childNode.metadata.source === 'local' && 'text' in m) {
              // Comparing potentially large text strings directly. Consider hashing if performance becomes an issue.
              return m.text === childNode.metadata.text;
          }
          return false; 
      })}
                           <Self
                                node={childNode}
                                level={level + 1}
			     isSelected={childIsSelected}
			     {activeConfigModules}
			     {expandedFolderPaths}
			     {getModule}
			     {onToggleSelect}
			     {onShowDetail}
			     {onSliderInput}
			     {onToggleExpand}
			   />
			{/each}
		{/if}

	<!-- === File Node === -->
	{:else if node.type === 'file'}
		<div class="node-content file">
			<input
				type="checkbox"
				checked={isSelectedProp}
				onchange={(e) => onToggleSelect(node.uiPath, e.currentTarget.checked, node.metadata)}
				class="checkbox"
			/>
			<div class="file-info" onclick ={() => onShowDetail(node.metadata)} style="cursor: pointer;">
				<IconDocumentRegular class="icon" />
				<span class="title">{node.metadata.title}</span>
			</div>
			{#if isSelectedProp && module}
				<input
					type="range"
					min="1"
					max="5"
					value={module.adherence_level ?? 3}
					oninput={(e) => onSliderInput(node.uiPath, parseInt(e.currentTarget.value))}
					class="slider"
					title={`Adherence Level: ${module.adherence_level ?? 3}`}
				/>
			{/if}
		</div>
	{/if}
</div>

<!-- === Styles === -->
<style>
	.node-container {
		margin-bottom: 0.25rem;
	}

	.node-content {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.1rem 0;
	}

	.icon {
		flex-shrink: 0;
		width: 1.1em;
		height: 1.1em;
		vertical-align: middle;
	}

	.chevron {
		flex-shrink: 0;
		width: 1.1em;
		height: 1.1em;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: var(--vscode-foreground);
		opacity: 0.8;
	}
	.chevron:hover {
		opacity: 1;
	}

	.title {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex-grow: 1;
		color: var(--vscode-foreground);
	}

	.bold {
		font-weight: 600;
	}

	.selection-count {
		font-size: 0.8em;
		color: var(--vscode-descriptionForeground);
		margin-right: 0.2rem;
		flex-shrink: 0;
	}

	.checkbox {
		margin-right: 0.2rem;
		flex-shrink: 0;
	}

	.file-info {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-grow: 1;
		min-width: 0;
		padding: 0.1rem 0.2rem;
		border-radius: 3px;
	}

	.file-info:hover {
		background-color: var(--vscode-list-hoverBackground);
	}

	.slider {
		margin-left: auto;
		flex-shrink: 0;
		width: 80px;
		height: 1rem;
		cursor: pointer;
	}

</style>