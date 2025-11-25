# 📋 Frontend Guide - Azure Cloud AI Visualizer

## 🏗️ Frontend Architecture Overview

The frontend is built with **React + TypeScript + Vite**, leveraging modern libraries to create a rich and interactive user experience.

### 🎯 Core Technologies

- **React 18** - UI Framework
- **TypeScript** - Static typing
- **Vite** - Build tool and dev server
- **TailwindCSS** - Utility-first styling
- **React Flow** - Interactive diagrams
- **Zustand** - State management
- **React Query** - Async data management
- **Shadcn/UI** - Reusable UI components

---

## 📂 Directory Structure

```
frontend/src/
├── components/         # Reusable components
│   ├── layout/        # Layout components (panels, bars)
│   ├── nodes/         # Custom nodes for React Flow
│   ├── edges/         # Custom edges for React Flow
│   ├── ui/            # Base UI components (buttons, modals, etc)
│   └── upload/        # Upload components
├── context/           # React contexts (Supabase, etc)
├── hooks/             # Custom hooks
├── lib/               # Utilities and APIs
├── pages/             # Main pages (Index, Workspace)
├── services/          # Data services
├── store/             # Zustand stores
└── data/              # Static data (Azure icons, etc)
```

---

## 🎨 Main Components

### 1. **Workspace.tsx** - Main Page
The workspace is the heart of the application where users create Azure architecture diagrams.

**Responsibilities:**
- Manage global diagram state (nodes and connections)
- Coordinate side panels (Chat, Assets, IaC)
- Auto-generate IaC code (Bicep/Terraform) based on diagram
- Persist data to Supabase
- Manage resource deployment

**Main State:**
```typescript
const [isChatOpen, setIsChatOpen] = useState(false);
const [isAssetsOpen, setIsAssetsOpen] = useState(false);
const [isIacOpen, setIsIacOpen] = useState(false);
const [footerHeight, setFooterHeight] = useState<number>(192);
const [generatedFiles, setGeneratedFiles] = useState<IaCFile[]>([]);
```

---

### 2. **TopBar** - Top Bar
Contains:
- Project title (editable)
- Save button
- Toggles to open side panels
- Project actions (rename, delete)

---

### 3. **ServicePalette** - Azure Services Palette
Left sidebar with all available Azure services for drag-and-drop onto canvas.

**Categories:**
- Compute, Storage, Networking
- Databases, AI + ML, Security
- Integration, DevOps, etc.

---

### 4. **DiagramCanvas** - Diagram Canvas
Central component using **React Flow** to create drag-and-drop diagrams.

**Features:**
- Drag & Drop services
- Connections between services
- Zoom/Pan
- Snap to grid
- Groups/containers
- Multiple selection

---

### 5. **InspectorPanel** - Inspector Panel
Right sidebar showing details of selected item:
- Node properties
- Bicep code editor (when available)
- Connection settings

---

### 6. **JobsDrawer** - Resizable Footer ⭐ NEW

The footer contains 4 main tabs:

#### **📊 Summary**
Shows project statistics:
- Number of nodes and connections
- Unique services
- Generated IaC files
- Bicep/Terraform code lines
- Warnings and errors

#### **💻 IaC**
Lists all generated IaC files:
- Auto-generated.bicep
- Auto-generated.tf
- Manual files
- Actions: View, Download, Deploy

#### **✅ Validation**
Shows validation results:
- Warnings
- Errors
- Validation status

#### **📝 Deploy Logs**
Real-time deployment logs stream (future)

**✨ Resize Functionality:**
- Draggable divider line between canvas and footer
- **Quick action buttons** for instant resize ⭐ NEW
- Minimum height: 150px
- Maximum height: 600px
- Default height: 192px
- Visual feedback on hover

**Quick Actions:**
- **Minimize button** (↓): Instantly sets footer to 150px height
- **Maximize button** (↑): Instantly sets footer to 450px height
- **Drag divider**: Smooth custom height adjustment

**How to use:**
1. Hover over the divider line above the footer
2. Use quick action buttons on the right side:
   - Click ↓ to minimize
   - Click ↑ to maximize
3. Or drag the divider for precise control

---

### 7. **ChatPanel** - AI Chat Panel
Right sidebar with chat for:
- Generate diagrams via natural language
- Ask questions about architecture
- Get best practice suggestions
- Modify existing diagrams

**Integration:**
- WebSocket for real-time communication
- Response streaming
- Message history
- Current diagram context

---

### 8. **IaCVisualization** - IaC Visualizer
Side panel to visualize and edit IaC code:
- Syntax highlighting
- Monaco editor
- Parameter preview
- Manual Bicep/Terraform generation

---

### 9. **AssetManager** - Asset Manager
Upload and manage:
- Architecture images
- Existing Terraform files
- Bicep templates
- Documentation

---

## 🔄 Data Flow

### IaC Auto-generation

```
1. User adds/modifies nodes on canvas
   ↓
2. diagramSignature changes (useEffect detects)
   ↓
3. 2s timer waits for more changes
   ↓
4. runAutoIac() is called
   ↓
5. generateIac() calls backend
   ↓
6. Backend uses AI to generate Bicep + Terraform
   ↓
7. persistIacArtifacts() saves to state and Supabase
   ↓
8. JobsDrawer updates with new files
```

### Supabase Persistence

```typescript
// Diagram is auto-saved when:
- Nodes or edges change (debounced)
- User clicks "Save"
- IaC is generated

// Data saved:
{
  diagram_state: { nodes, edges, saved_at },
  bicep_template: string,
  bicep_parameters: object,
  terraform_template: string,
  terraform_parameters: object
}
```

---

## 🎯 Zustand Stores

### `diagramStore.ts`
Manages diagram state:
```typescript
{
  nodes: Node[],
  edges: Edge[],
  addNode: (node) => void,
  removeNode: (id) => void,
  updateNode: (id, data) => void,
  addEdge: (edge) => void,
  clearDiagram: () => void,
  loadDiagram: (nodes, edges) => void
}
```

### `iacStore.ts`
Manages IaC templates:
```typescript
{
  currentBicepTemplate: string | null,
  pendingBicepTemplateUpdate: string | null,
  setBicepTemplate: (template) => void,
  consumePendingBicepTemplate: () => string | null,
  clear: () => void
}
```

---

## 🎨 Implemented UX/UI Improvements

### ✅ 1. Resizable Footer with Quick Actions

**Problem:** Footer had fixed height (192px), limiting content visibility.

**Solution:**
- Created `ResizableDivider` component
- Interactive visual divider with hover feedback
- Vertical drag to adjust height
- **Quick action buttons for instant resize** ⭐ NEW
- Min/max limits for consistent UX
- State persisted during session

**Features:**
```typescript
// ResizableDivider Component
- Draggable divider line
- Minimize button (↓) - Sets to 150px
- Maximize button (↑) - Sets to 450px
- Smooth transitions
- Visual hover states
- Positioned on right side of divider
```

**Code:**
```typescript
// Quick action buttons in ResizableDivider
<div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-1">
  {onMinimize && (
    <button onClick={onMinimize} title="Minimize footer">
      <svg><!-- Down arrow icon --></svg>
    </button>
  )}
  {onMaximize && (
    <button onClick={onMaximize} title="Maximize footer">
      <svg><!-- Up arrow icon --></svg>
    </button>
  )}
</div>

// Usage in Workspace
<ResizableDivider 
  onResize={setFooterHeight}
  onMinimize={() => setFooterHeight(150)}
  onMaximize={() => setFooterHeight(450)}
  minHeight={150}
  maxHeight={600}
/>
```

**Benefits:**
- ✅ More flexibility to view logs
- ✅ Adaptable to different resolutions
- ✅ Better use of vertical space
- ✅ Clear visual feedback to user
- ✅ **One-click resize for quick access** ⭐
- ✅ Smooth drag for precise control

---

### 🎯 2. Future Improvement Suggestions

#### **A. Customizable Themes**
- Light/dark mode already exists
- Add more variations (High Contrast, Azure Blue, etc)
- Save preference in localStorage

#### **B. Keyboard Shortcuts**
```typescript
// useKeyboardShortcuts hook already exists
// Expand to:
Ctrl+S     → Save
Ctrl+Z     → Undo
Ctrl+Y     → Redo
Delete     → Delete selected
Ctrl+C/V   → Copy/Paste nodes
Ctrl+D     → Duplicate
```

#### **C. Minimap in Canvas**
- Overview of diagram
- Quick navigation in large diagrams
- React Flow already supports it

#### **D. Guided Tour**
- Intro.js or similar
- Guide for new users
- Highlight main features

#### **E. Version History**
- Git-like versioning for diagrams
- View changes over time
- Restore previous versions

#### **F. Real-time Collaboration**
- Multiple users on same diagram
- Other users' cursors
- WebSocket + Supabase Realtime

#### **G. Advanced Export**
- High-quality PNG/SVG
- PDF with documentation
- Drawio/Visio export

#### **H. Pre-configured Templates**
- Azure Landing Zones
- Architecture patterns (3-tier, microservices)
- Well-Architected Framework

---

## 🧩 How to Add New Features

### Add New Tab in Footer

1. **Edit `JobsDrawer.tsx`:**
```typescript
<TabsList className="mx-4 mt-3 grid w-auto grid-cols-5"> {/* cols-4 → cols-5 */}
  {/* ... existing tabs ... */}
  <TabsTrigger value="new-feature" className="gap-2">
    <Icon icon="mdi:new-icon" />
    New Feature
  </TabsTrigger>
</TabsList>

<TabsContent value="new-feature" className="flex-1 overflow-y-auto px-4 pb-4">
  {/* Tab content */}
</TabsContent>
```

### Add New Side Panel

1. **Create component** in `components/layout/NewPanel.tsx`
2. **Add state** in `Workspace.tsx`:
```typescript
const [isNewPanelOpen, setIsNewPanelOpen] = useState(false);
```
3. **Add toggle** in `TopBar`
4. **Render** in layout

---

## 🐛 Debugging

### React DevTools
- Inspect components
- View props/state
- Performance profiling

### Zustand DevTools
```typescript
import { devtools } from 'zustand/middleware';

export const useDiagramStore = create(
  devtools((set) => ({
    // ...
  }), { name: 'DiagramStore' })
);
```

### Network Tab
- Verify API calls
- WebSocket messages
- Supabase queries

### Strategic Console Logs
```typescript
console.log('[Workspace] Auto IaC regeneration completed');
console.error('[Workspace] Failed to load diagram state', error);
```

---

## 📦 Build and Deploy

### Development
```bash
cd frontend
npm install
npm run dev
```

### Production Build
```bash
npm run build
# Generates dist/ with optimized assets
```

### Preview Build
```bash
npm run preview
```

### Deploy
- Vercel (recommended for frontend)
- Azure Static Web Apps
- Netlify
- Docker (see Dockerfile.frontend)

---

## 🎓 Learning Resources

- [React Flow Docs](https://reactflow.dev/)
- [Zustand Guide](https://github.com/pmndrs/zustand)
- [TailwindCSS Docs](https://tailwindcss.com/)
- [Shadcn/UI Components](https://ui.shadcn.com/)
- [Vite Guide](https://vitejs.dev/)

---

## 📝 Conclusion

The frontend is a modern and well-structured React application with:
- ✅ Reusable and modular components
- ✅ Predictable state management (Zustand)
- ✅ Responsive and accessible UI
- ✅ Backend integration via REST API + WebSocket
- ✅ Supabase persistence
- ✅ Intelligent IaC auto-generation
- ⭐ **NEW:** Resizable footer with quick action buttons for better UX

The architecture allows for easy extension and maintenance, following React and TypeScript best practices.

---

## 🆕 Recent Updates

### November 2025
- ✅ Added resizable footer with drag functionality
- ✅ Implemented quick action buttons (minimize/maximize)
- ✅ Enhanced user experience with instant resize options
- ✅ Improved visual feedback on hover states
- ✅ Optimized for better vertical space usage
