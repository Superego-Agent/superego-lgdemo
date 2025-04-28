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
		<div class="node-content folder" onclick={() => onToggleExpand(node)} title="Toggle folder">
			<!-- Removed onclick from chevron span, parent div handles it -->
			<span class="chevron" style="cursor: pointer;">
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
		<div class="node-content file" onclick={() => onToggleSelect(node.uiPath, !isSelectedProp, node.metadata)} title="Toggle selection">
			<input
				type="checkbox"
				checked={isSelectedProp}
				onchange={(e) => onToggleSelect(node.uiPath, e.currentTarget.checked, node.metadata)}
				class="checkbox"
			/>
			<!-- Remove onclick from file-info, handle clicks on specific elements -->
			<div class="file-info">
				<!-- Wrap icon and title for separate click/hover -->
				<!-- Removed stopPropagation modifier -->
				<span class="file-details-clickable" onclick={(event) => { event.stopPropagation(); onShowDetail(node.metadata); }} title="View constitution details">
					<IconDocumentRegular class="icon file-icon" /> <!-- Added file-icon class -->
					<span class="title">{node.metadata.title}</span>
				</span>
			</div>
			{#if isSelectedProp && module}
				<!-- Wrapper for slider and level display -->
				<div class="slider-container">
					<input
						type="range"
						min="1"
						max="5"
						value={module.adherence_level ?? 3}
						oninput={(e) => onSliderInput(node.uiPath, parseInt(e.currentTarget.value))}
						class="slider"
						title={`Adherence Level: ${module.adherence_level ?? 3}`}
						onclick={(e) => e.stopPropagation()}
					/>
					<span class="level-display">
						{module.adherence_level ?? 3}<span class="dimmed">/5</span>
					</span>
				</div>
			{/if}
		</div>
	{/if}
</div>

<!-- === Styles === -->
<style lang="scss">
	.node-container {
		/* Removed margin-bottom, will apply to specific node types */
	}

	.node-content {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.1rem 0.2rem; // Add slight horizontal padding for hover bg
		border-radius: 3px; // Rounded corners for hover bg
		transition: background-color 0.15s ease; // Smooth hover transition
		cursor: pointer; // Indicate clickability
	}

	.node-content:hover {
		background-color: var(--vscode-list-hoverBackground, rgba(128, 128, 128, 0.1)); // Subtle hover background
	}

	/* Add specific margins for folder and file types */
	.node-content.folder {
		margin-bottom: 0.25rem; /* Keep original spacing for folders */
	}

	.node-content.file {
		margin-bottom: 0.05rem; /* Further reduce spacing for files */
		padding-top: 0rem; /* Remove top padding for files */
		padding-bottom: 0rem; /* Remove bottom padding for files */
	}

	.icon {
		flex-shrink: 0;
		width: 1.1em;
		height: 1.1em;
		vertical-align: middle;
	}

	.file-icon {
		transition: transform 0.15s ease, filter 0.15s ease; /* Smooth transition for hover */
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
		flex-grow: 1; // Revert to original flex-grow
		// min-width: 0; // Remove min-width
		padding: 0.1rem 0.2rem;
		border-radius: 3px;
	}

	/* Remove hover from file-info, apply to node-content */
	/* .file-info:hover {
		background-color: var(--vscode-list-hoverBackground);
	} */

	/* Style for the clickable icon/title area */
	.file-details-clickable {
		display: inline-flex; /* Align icon and title */
		align-items: center;
		gap: 0.4rem; /* Match gap in file-info */
		cursor: pointer;
		padding: 0.1rem 0.2rem; /* Match padding */
		border-radius: 3px; /* Match radius */
		transition: background-color 0.15s ease;
	}

	.file-details-clickable:hover {
		background-color: var(--vscode-list-hoverBackground); /* Highlight on hover */
		/* Optionally add text decoration or color change */
		/* color: var(--primary); */
	}

	/* Add hover effect specifically for the file icon within the clickable area */
	.file-details-clickable:hover .file-icon {
		transform: scale(1.2); /* Grow the icon */
		filter: brightness(1.2); /* Brighten the icon */
	}

	.slider-container {
		display: flex;
		align-items: center;
		gap: var(--space-sm); // Keep gap
		margin-left: auto; // Restore margin-left: auto
		width: 160px; // Give container explicit width
		flex-shrink: 0; // Keep flex-shrink
	}

	.slider {
		// margin-left: auto; // Moved margin to container
		flex-shrink: 0; // Keep shrink 0
		width: 120px; // Increase fixed width
		height: 1rem;
		cursor: pointer;
		accent-color: var(--primary); // Style slider color
	}

	.level-display {
		font-size: 0.9em; // Increased font size
		color: var(--text-primary); // Base color for the number
		min-width: 25px; // Ensure space for "X/5"
		text-align: right;
		flex-shrink: 0;

		.dimmed {
			color: var(--text-secondary); // Dimmer color for "/5"
			opacity: 0.7; // Slightly dimmer
		}
	}

</style>