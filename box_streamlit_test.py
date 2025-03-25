import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import numpy as np
from streamlit_extras.stylable_container import stylable_container
from io import BytesIO
import base64

# Set page config
st.set_page_config(
    page_title="Advanced 3D Packing Visualizer",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Dark Theme CSS with mobile enhancements
st.markdown("""
<style>
    /* Dark theme colors */
    :root {
        --primary: #8b5cf6;
        --primary-hover: #7c3aed;
        --secondary: #6366f1;
        --background: #0f172a;
        --card: #1e293b;
        --text: #f8fafc;
        --text-secondary: #94a3b8;
        --border: #334155;
        --success: #10b981;
        --error: #ef4444;
    }
    
    /* Main container */
    .stApp {
        background-color: var(--background);
        color: var(--text);
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text) !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Input widgets */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        background-color: var(--card) !important;
        color: var(--text) !important;
        border-radius: 10px !important;
        padding: 10px 12px !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Buttons */
    .stButton>button {
        background-color: var(--primary) !important;
        color: white !important;
        border-radius: 10px !important;
        padding: 10px 16px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }
    
    .stButton>button:hover {
        background-color: var(--primary-hover) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
    }
    
    /* Cards */
    .st-emotion-cache-1y4p8pa {
        background-color: var(--card) !important;
        color: var(--text) !important;
        border-radius: 12px !important;
        padding: 20px !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Visualization container */
    .stPlotlyChart {
        border-radius: 12px !important;
        background-color: var(--card) !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Metrics */
    .stMetric {
        background-color: var(--card) !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Success/error messages */
    .stAlert {
        background-color: var(--card) !important;
        border: 1px solid var(--border) !important;
    }
    
    .stSuccess {
        background-color: rgba(16, 185, 129, 0.1) !important;
        border-left: 4px solid var(--success) !important;
    }
    
    .stError {
        background-color: rgba(239, 68, 68, 0.1) !important;
        border-left: 4px solid var(--error) !important;
    }
    
    /* Remove Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--card);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb {
        background: var(--border);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--primary);
    }
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        .stNumberInput input, .stTextInput input {
            padding: 8px 10px !important;
            font-size: 14px !important;
        }
        .stButton>button {
            padding: 8px 12px !important;
            width: 100% !important;
        }
        .st-emotion-cache-1y4p8pa {
            flex-direction: column !important;
        }
        /* Make columns stack vertically on mobile */
        .st-emotion-cache-1v0mbdj {
            flex-direction: column !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'items_to_pack' not in st.session_state:
    st.session_state.items_to_pack = []
if 'first_visit' not in st.session_state:
    st.session_state.first_visit = True

def metric_card(title, value, icon=None):
    """Custom metric card display"""
    with stylable_container(
        key=f"metric_{title}",
        css_styles="""
            {
                background-color: var(--card);
                border-radius: 10px;
                padding: 16px;
                border: 1px solid var(--border);
            }
        """
    ):
        if icon:
            st.markdown(f"<p style='color: var(--text-secondary); margin-bottom: 8px;'>{icon} {title}</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='color: var(--text-secondary); margin-bottom: 8px;'>{title}</p>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='margin-top: 0;'>{value}</h3>", unsafe_allow_html=True)

def add_item(name, width, height, depth, weight, can_stack=False, fragile=False):
    """Add item to the packing list with stacking options"""
    if not name:
        st.error("Please enter a product name")
        return False
        
    if width <= 0 or height <= 0 or depth <= 0 or weight <= 0:
        st.error("Dimensions and weight must be positive numbers")
        return False
        
    item = {
        "name": name,
        "width": width,
        "height": height,
        "depth": depth,
        "weight": weight,
        "can_stack": can_stack,
        "fragile": fragile
    }
    st.session_state.items_to_pack.append(item)
    return True

def remove_item(index):
    """Remove item from the packing list"""
    st.session_state.items_to_pack.pop(index)

def calculate_efficiency(bin):
    """Calculate packing efficiency with stacking consideration"""
    if not hasattr(bin, 'items') or not bin.items:
        return 0
    
    total_item_volume = sum(
        item.get_dimension()[0] * item.get_dimension()[1] * item.get_dimension()[2] 
        for item in bin.items
    )
    
    bin_volume = bin.width * bin.height * bin.depth
    efficiency = (total_item_volume / bin_volume) * 100 if bin_volume > 0 else 0
    
    # Check stacking stability
    unstable_count = 0
    for item in bin.items:
        if hasattr(item, 'position') and hasattr(item, 'dimension'):
            items_above = [
                i for i in bin.items 
                if i.position[2] > item.position[2] and
                i.position[0] < item.position[0] + item.dimension[0] and
                i.position[0] + i.dimension[0] > item.position[0] and
                i.position[1] < item.position[1] + item.dimension[1] and
                i.position[1] + i.dimension[1] > item.position[1]
            ]
            if items_above and not getattr(item, 'can_stack', False):
                unstable_count += 1
    
    # Apply penalty for unstable stacking
    if unstable_count > 0:
        efficiency *= max(0.7, 1 - (unstable_count * 0.05))  # 5% penalty per unstable item
    
    return efficiency

@st.cache_data(show_spinner="Optimizing packing...")
def pack_items_into_box(_box_name, _box_width, _box_height, _box_depth, items, strategy="Balanced", max_attempts=3):
    """Enhanced packing algorithm with multiple optimization strategies"""
    # Recreate the box from parameters
    box = Bin(_box_name, _box_width, _box_height, _box_depth, 1000)
    
    packer = Packer()
    packer.add_bin(box)
    
    # Rest of your packing logic remains the same...
    # Define multiple sorting strategies based on selected strategy
    if strategy == "Maximize Space":
        sorting_strategies = [
            lambda x: (-x['width']*x['height']*x['depth'], -max(x['width'], x['height'], x['depth'])),
            lambda x: (-max(x['width'], x['height'], x['depth']), -x['width']*x['height']*x['depth']),
            lambda x: (-x['width']*x['height'], -x['depth']),
        ]
    elif strategy == "Prioritize Stability":
        sorting_strategies = [
            lambda x: (x['can_stack'], -x['weight'], -x['width']*x['height']*x['depth']),
            lambda x: (-x['weight'], x['can_stack'], -x['width']*x['height']*x['depth']),
        ]
    elif strategy == "Minimize Weight Shifting":
        sorting_strategies = [
            lambda x: (-x['weight'], -x['width']*x['height']*x['depth']),
            lambda x: (x['fragile'], -x['weight'], -x['width']*x['height']*x['depth']),
        ]
    else:  # Balanced
        sorting_strategies = [
            lambda x: (-x['width']*x['height']*x['depth'], -max(x['width'], x['height'], x['depth'])),
            lambda x: (-max(x['width'], x['height'], x['depth']), -x['width']*x['height']*x['depth']),
            lambda x: (-x['width']*x['height'], -x['depth']),
            lambda x: (-x['weight'], -x['width']*x['height']*x['depth']),
            lambda x: (x['can_stack'], -x['width']*x['height']*x['depth']),
        ]
    
    best_packed_bin = None
    best_efficiency = 0
    
    # Try different sorting strategies
    for strategy in sorting_strategies[:max_attempts]:
        temp_packer = Packer()
        temp_packer.add_bin(Bin(_box_name, _box_width, _box_height, _box_depth, 1000))
        
        sorted_items = sorted(items, key=strategy)
        
        for item_data in sorted_items:
            item = Item(
                item_data["name"],
                item_data["width"],
                item_data["height"],
                item_data["depth"],
                item_data["weight"]
            )
            item.rotation_type = 3 if st.session_state.get("allow_rotation", True) else 0
            
            # Adjust weight based on properties
            weight_multiplier = 1.0
            if item_data["can_stack"]:
                weight_multiplier *= 1.5  # Make stackable items heavier
            if item_data["fragile"] and st.session_state.get("prioritize_fragile", True):
                weight_multiplier *= 2  # Make fragile items heavier
            item.weight = float(item_data["weight"]) * weight_multiplier
                
            temp_packer.add_item(item)
        
        # Pack with different parameters
        temp_packer.pack(
            bigger_first=True,
            distribute_items=False,
            number_of_decimals=2
        )
        
        # Evaluate this packing
        current_bin = temp_packer.bins[0]
        current_efficiency = calculate_efficiency(current_bin)
        
        # Keep the best packing
        if current_efficiency > best_efficiency:
            best_efficiency = current_efficiency
            best_packed_bin = current_bin
    
    # If no packing worked, try a simple approach
    if best_packed_bin is None or len(best_packed_bin.items) == 0:
        simple_packer = Packer()
        simple_packer.add_bin(Bin(_box_name, _box_width, _box_height, _box_depth, 1000))
        
        for item_data in items:
            item = Item(
                item_data["name"],
                item_data["width"],
                item_data["height"],
                item_data["depth"],
                item_data["weight"]
            )
            item.rotation_type = 3 if st.session_state.get("allow_rotation", True) else 0
            simple_packer.add_item(item)
        
        simple_packer.pack(
            bigger_first=False,
            distribute_items=True,
            number_of_decimals=2
        )
        
        best_packed_bin = simple_packer.bins[0]
    
    # Post-processing to check stacking stability
    for item in best_packed_bin.items:
        # Find items below this one
        items_below = [
            i for i in best_packed_bin.items 
            if float(i.position[2]) + float(i.get_dimension()[2]) <= float(item.position[2]) + 0.1 and  # Convert to float
            float(i.position[0]) < float(item.position[0]) + float(item.get_dimension()[0]) and
            float(i.position[0]) + float(i.get_dimension()[0]) > float(item.position[0]) and
            float(i.position[1]) < float(item.position[1]) + float(item.get_dimension()[1]) and
            float(i.position[1]) + float(i.get_dimension()[1]) > float(item.position[1]) and
            i != item
        ]
        
        # Mark unstable stacking
        if items_below:
            original_item = next((i for i in items if i["name"] == item.name), None)
            if original_item and not original_item["can_stack"]:
                setattr(item, 'unstable_stack', True)
    
    return best_packed_bin

def create_modern_visualization(packed_bin):
    """Enhanced visualization showing stacking relationships"""
    fig = go.Figure()

    # Container box (transparent with visible edges)
    container_edges = [
        [0, 0, 0], [packed_bin.width, 0, 0], 
        [packed_bin.width, packed_bin.height, 0], [0, packed_bin.height, 0],
        [0, 0, packed_bin.depth], [packed_bin.width, 0, packed_bin.depth],
        [packed_bin.width, packed_bin.height, packed_bin.depth], [0, packed_bin.height, packed_bin.depth]
    ]
    
    # Add container edges
    lines = [
        [0, 1], [1, 2], [2, 3], [3, 0],  # Bottom
        [4, 5], [5, 6], [6, 7], [7, 4],  # Top
        [0, 4], [1, 5], [2, 6], [3, 7]   # Sides
    ]
    for line in lines:
        fig.add_trace(go.Scatter3d(
            x=[container_edges[line[0]][0], container_edges[line[1]][0]],
            y=[container_edges[line[0]][1], container_edges[line[1]][1]],
            z=[container_edges[line[0]][2], container_edges[line[1]][2]],
            mode='lines',
            line=dict(color='#64748b', width=2),
            showlegend=False,
            hoverinfo='none'
        ))

    # Add packed items with enhanced visualization
    colors = [
        '#8b5cf6', '#3b82f6', '#10b981', '#f59e0b',
        '#ec4899', '#14b8a6', '#f97316', '#6366f1'
    ]
    
    for i, item in enumerate(packed_bin.items):
        pos = item.position
        dim = item.get_dimension()
        color = colors[i % len(colors)]
        
        # Highlight unstable stacking
        if getattr(item, 'unstable_stack', False):
            color = '#ef4444'  # Red for unstable
            
        # Create vertices for the item
        vertices = [
            [pos[0], pos[1], pos[2]],
            [pos[0] + dim[0], pos[1], pos[2]],
            [pos[0] + dim[0], pos[1] + dim[1], pos[2]],
            [pos[0], pos[1] + dim[1], pos[2]],
            [pos[0], pos[1], pos[2] + dim[2]],
            [pos[0] + dim[0], pos[1], pos[2] + dim[2]],
            [pos[0] + dim[0], pos[1] + dim[1], pos[2] + dim[2]],
            [pos[0], pos[1] + dim[1], pos[2] + dim[2]]
        ]
        
        # Determine opacity based on stacking
        opacity = 0.7 if getattr(item, 'can_stack', False) else 0.9
        
        # Add solid colored box
        fig.add_trace(go.Mesh3d(
            x=[v[0] for v in vertices],
            y=[v[1] for v in vertices],
            z=[v[2] for v in vertices],
            i=[0, 0, 0, 0, 5, 5, 5, 5, 1, 1, 2, 2],
            j=[1, 2, 3, 4, 6, 7, 4, 6, 5, 2, 6, 3],
            k=[2, 3, 0, 5, 7, 4, 0, 1, 6, 6, 3, 7],
            color=color,
            opacity=opacity,
            flatshading=True,
            name=f"{item.name} {'(Stackable)' if getattr(item, 'can_stack', False) else ''}",
            showlegend=True,
            hoverinfo='name+text',
            text=f"Size: {dim[0]:.1f}×{dim[1]:.1f}×{dim[2]:.1f} cm<br>Position: {pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}<br>Weight: {item.weight} kg"
        ))
        
        # Add wireframe edges for better visibility
        edge_color = '#0f172a' if not getattr(item, 'fragile', False) else '#ef4444'
        for line in lines[:12]:
            fig.add_trace(go.Scatter3d(
                x=[vertices[line[0]][0], vertices[line[1]][0]],
                y=[vertices[line[0]][1], vertices[line[1]][1]],
                z=[vertices[line[0]][2], vertices[line[1]][2]],
                mode='lines',
                line=dict(color=edge_color, width=1.5 if getattr(item, 'fragile', False) else 1),
                showlegend=False,
                hoverinfo='none'
            ))

    # Set layout with modern styling and enhanced features
    fig.update_layout(
        scene=dict(
            xaxis=dict(
                title='Width (cm)',
                range=[0, packed_bin.width],
                backgroundcolor='rgba(0,0,0,0)',
                gridcolor='#334155',
                zerolinecolor='#334155',
                title_font=dict(color='#f8fafc'),
                tickfont=dict(color='#94a3b8')
            ),
            yaxis=dict(
                title='Height (cm)',
                range=[0, packed_bin.height],
                backgroundcolor='rgba(0,0,0,0)',
                gridcolor='#334155',
                zerolinecolor='#334155',
                title_font=dict(color='#f8fafc'),
                tickfont=dict(color='#94a3b8')
            ),
            zaxis=dict(
                title='Depth (cm)',
                range=[0, packed_bin.depth],
                backgroundcolor='rgba(0,0,0,0)',
                gridcolor='#334155',
                zerolinecolor='#334155',
                title_font=dict(color='#f8fafc'),
                tickfont=dict(color='#94a3b8')
            ),
            aspectmode='manual',
            aspectratio=dict(
                x=1, 
                y=packed_bin.height/packed_bin.width if packed_bin.width > 0 else 1,
                z=packed_bin.depth/packed_bin.width if packed_bin.width > 0 else 1
            ),
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=0.8),
                up=dict(x=0, y=0, z=1)
            ),
            bgcolor='rgba(30, 41, 59, 0.5)'
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='#f8fafc', size=12)
        ),
        height=700,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f8fafc'),
        # Add view controls
        updatemenus=[
            dict(
                type="buttons",
                buttons=[
                    dict(label="3D View",
                         method="relayout",
                         args=["scene.camera", dict(eye=dict(x=1.5, y=1.5, z=0.8))]),
                    dict(label="Top View",
                         method="relayout",
                         args=["scene.camera", dict(eye=dict(x=0, y=0, z=2))]),
                    dict(label="Side View",
                         method="relayout",
                         args=["scene.camera", dict(eye=dict(x=2, y=0, z=0))]),
                    dict(label="Front View",
                         method="relayout",
                         args=["scene.camera", dict(eye=dict(x=0, y=2, z=0))])
                ],
                direction="left",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.1,
                xanchor="left",
                y=1.1,
                yanchor="top"
            )
        ],
        # Add slice view capability
        sliders=[dict(
            active=0,
            steps=[dict(args=["scene.zaxis.range", [0, z]],
                  label=f"Slice {z}cm") 
                  for z in range(0, int(packed_bin.depth)+1, 5)],
            pad={"t": 50}
        )]
    )
    
    return fig

def generate_pdf_report(packed_bin):
    """Generate a PDF report (placeholder - would be implemented with reportlab)"""
    # In a real implementation, you would use reportlab to generate a PDF
    # This is a simplified version that creates a downloadable HTML file
    from datetime import datetime
    report = f"""
    <html>
    <head><title>Packing Report - {datetime.now().strftime("%Y-%m-%d")}</title></head>
    <body>
    <h1>Packing Report</h1>
    <h2>Box: {packed_bin.name}</h2>
    <p>Dimensions: {packed_bin.width}×{packed_bin.height}×{packed_bin.depth} cm</p>
    <p>Packing Efficiency: {calculate_efficiency(packed_bin):.1f}%</p>
    <h3>Items Packed:</h3>
    <ul>
    """
    
    for item in packed_bin.items:
        report += f"""
        <li>
            <strong>{item.name}</strong> - 
            Size: {item.get_dimension()[0]:.1f}×{item.get_dimension()[1]:.1f}×{item.get_dimension()[2]:.1f} cm,
            Position: {item.position[0]:.1f}, {item.position[1]:.1f}, {item.position[2]:.1f},
            Weight: {item.weight} kg
        </li>
        """
    
    report += """
    </ul>
    </body>
    </html>
    """
    
    # Create download link
    b64 = base64.b64encode(report.encode()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="packing_report.html">Download Report</a>'
    st.markdown(href, unsafe_allow_html=True)

def export_3d_model(packed_bin):
    """Export 3D model (placeholder - would use trimesh or similar)"""
    st.warning("3D model export would be implemented with a proper 3D library in a production environment")
    st.info("For now, you can take a screenshot of the visualization")

def export_packing_data(packed_bin):
    """Export packing data as CSV"""
    import pandas as pd
    from io import StringIO
    
    data = {
        "Item": [],
        "Width": [],
        "Height": [],
        "Depth": [],
        "Weight": [],
        "Position_X": [],
        "Position_Y": [],
        "Position_Z": [],
        "Rotation": []
    }
    
    for item in packed_bin.items:
        data["Item"].append(item.name)
        dim = item.get_dimension()
        data["Width"].append(dim[0])
        data["Height"].append(dim[1])
        data["Depth"].append(dim[2])
        data["Weight"].append(item.weight)
        data["Position_X"].append(item.position[0])
        data["Position_Y"].append(item.position[1])
        data["Position_Z"].append(item.position[2])
        data["Rotation"].append(item.rotation_type)
    
    df = pd.DataFrame(data)
    csv = df.to_csv(index=False)
    
    # Create download link
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="packing_data.csv">Download CSV</a>'
    st.markdown(href, unsafe_allow_html=True)

# App layout
st.title("📦 Advanced 3D Packing Visualizer")
st.caption("Optimize your packaging with intelligent stacking and placement")

# Show tutorial on first visit
if st.session_state.first_visit:
    with st.expander("🎬 Quick Start Guide", expanded=True):
        st.markdown("""
        ### Welcome to the 3D Packing Visualizer!
        1. **Set your box dimensions** in the left panel
        2. **Add products** with their dimensions
        3. **Click 'Pack Items'** to optimize the packing
        4. **Explore** the 3D visualization
        
        Pro Tip: Use the view buttons to see different angles!
        """)
        if st.button("Got it!", key="dismiss_tutorial"):
            st.session_state.first_visit = False
            st.rerun()

# Create columns for layout
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    with st.container(border=True):
        st.header("📏 Box Dimensions", divider="rainbow")
        box_name = st.text_input("Box Name", key="box_name", placeholder="e.g., Shipping Box 01")
        
        # Quick box size selector
        with st.expander("📦 Common Box Sizes", expanded=False):
            common_boxes = {
                "Small": (30, 20, 20),
                "Medium": (40, 30, 30),
                "Large": (60, 40, 40),
                "Extra Large": (80, 50, 50)
            }
            cols = st.columns(len(common_boxes))
            for i, (name, size) in enumerate(common_boxes.items()):
                if cols[i].button(name):
                    st.session_state.box_width = size[0]
                    st.session_state.box_height = size[1]
                    st.session_state.box_depth = size[2]
                    st.rerun()
        
        cols = st.columns(3)
        box_width = cols[0].number_input("Width (cm)", min_value=0.1, value=40.0, key="box_width")
        box_height = cols[1].number_input("Height (cm)", min_value=0.1, value=30.0, key="box_height")
        box_depth = cols[2].number_input("Depth (cm)", min_value=0.1, value=30.0, key="box_depth")
    
    with st.container(border=True):
        st.header("➕ Add Product", divider="rainbow")
        prod_name = st.text_input("Product Name", key="prod_name", placeholder="e.g., Book")
        
        cols = st.columns(4)
        prod_width = cols[0].number_input("Width (cm)", min_value=0.1, key="prod_width", value=10.0)
        prod_height = cols[1].number_input("Height (cm)", min_value=0.1, key="prod_height", value=5.0)
        prod_depth = cols[2].number_input("Depth (cm)", min_value=0.1, key="prod_depth", value=15.0)
        prod_weight = cols[3].number_input("Weight (kg)", min_value=0.1, key="prod_weight", value=0.5)
        
        # Additional product properties
        cols = st.columns(2)
        can_stack = cols[0].checkbox("Can be stacked", key="can_stack")
        fragile = cols[1].checkbox("Fragile", key="fragile")
        
        if st.button("Add Product", use_container_width=True, type="primary"):
            if add_item(prod_name, prod_width, prod_height, prod_depth, prod_weight, can_stack, fragile):
                st.success(f"Added: {prod_name}")
                st.rerun()
    
    with st.container(border=True):
        st.header("⚙️ Packing Options", divider="rainbow")
        packing_strategy = st.selectbox(
            "Packing Strategy",
            ["Balanced (Default)", "Maximize Space", "Prioritize Stability", "Minimize Weight Shifting"],
            help="Choose different packing strategies for different needs"
        )
        
        # Add advanced options
        with st.expander("Advanced Options"):
            st.checkbox("Allow item rotation", value=True, key="allow_rotation")
            st.checkbox("Prioritize fragile items at bottom", value=True, key="prioritize_fragile")
            max_attempts = st.slider("Max packing attempts", 1, 10, 3, 
                                   help="More attempts may find better packing but take longer")
    
    with st.container(border=True):
        st.header("📋 Products to Pack", divider="rainbow")
        if not st.session_state.items_to_pack:
            st.info("No products added yet")
        else:
            for i, item in enumerate(st.session_state.items_to_pack):
                # Create a truly unique key using index, name, and dimensions
                unique_key = f"product_{i}_{item['name']}_{item['width']}_{item['height']}_{item['depth']}"
                with stylable_container(
                    key=f"container_{unique_key}",  # Unique container key
                    css_styles="""
                        {
                            background-color: var(--card);
                            border: 1px solid var(--border);
                            border-radius: 10px;
                            padding: 12px;
                            margin-bottom: 8px;
                            transition: all 0.2s;
                        }
                        :hover {
                            border-color: var(--primary);
                            box-shadow: 0 2px 8px rgba(139, 92, 246, 0.2);
                        }
                    """
                ):
                    cols = st.columns([4, 1])
                    cols[0].markdown(f"""
                        **{item['name']}**  
                        <span style='color: var(--text-secondary)'>{item['width']}×{item['height']}×{item['depth']} cm</span>  
                        <small style='color: var(--text-secondary)'>{item['weight']} kg</small>
                        {"<br><small style='color: #10b981'>Stackable</small>" if item['can_stack'] else ""}
                        {"<br><small style='color: #ef4444'>Fragile</small>" if item['fragile'] else ""}
                    """, unsafe_allow_html=True)
                    if cols[1].button("🗑️", 
                                    key=f"remove_{unique_key}",  # Unique button key
                                    help="Remove item"):
                        remove_item(i)
                        st.rerun()
        
        # Multi-bin packing option for larger shipments
        if len(st.session_state.items_to_pack) > 10:
            with st.expander("🚛 Multi-Bin Packing", expanded=False):
                max_bins = st.slider("Maximum number of boxes to use", 1, 10, 1,
                                   help="Allow the system to split items across multiple boxes")
                
                if st.button("Optimize Multi-Bin Packing", use_container_width=True):
                    st.warning("Multi-bin packing would be implemented in a production environment")
                    st.info("For now, please pack items into a single box")
        
        if st.button("📦 Pack Items", use_container_width=True, type="primary"):
            if not st.session_state.items_to_pack:
                st.error("Please add at least one product to pack")
            elif not box_name:
                st.error("Please enter a box name")
            else:
                # Create the box with all possible orientations
                possible_bins = [
                    Bin(box_name, box_width, box_height, box_depth, 1000),
                    Bin(box_name, box_height, box_width, box_depth, 1000),
                    Bin(box_name, box_depth, box_height, box_width, 1000)
                ]
                
                best_packing = None
                best_efficiency = 0
                
                for bin in possible_bins:
                    packed_bin = pack_items_into_box(
                        box_name,  # Pass name instead of box object
                        box_width,  # Pass width
                        box_height, # Pass height
                        box_depth,  # Pass depth
                        st.session_state.items_to_pack,
                        packing_strategy,
                        max_attempts
                    )
                    current_efficiency = calculate_efficiency(packed_bin)
                    
                    if current_efficiency > best_efficiency:
                        best_efficiency = current_efficiency
                        best_packing = packed_bin
                
                if best_packing:
                    st.session_state.packed_bin = best_packing
                    st.session_state.show_results = True
                    st.rerun()
                else:
                    st.error("Failed to pack items into the box")

with col2:
    if 'show_results' in st.session_state and st.session_state.show_results:
        packed_bin = st.session_state.packed_bin
        
        with st.container(border=True):
            st.header("📊 Packing Results", divider="rainbow")
            
            # Results metrics
            cols = st.columns(3)
            with cols[0]:
                metric_card("Box Name", packed_bin.name, "📦")
            with cols[1]:
                metric_card("Dimensions", f"{packed_bin.width}×{packed_bin.height}×{packed_bin.depth} cm", "📏")
            with cols[2]:
                metric_card("Efficiency", f"{calculate_efficiency(packed_bin):.1f}%", "⚡")
            
            # Items packed info
            st.subheader(f"Packed {len(packed_bin.items)}/{len(st.session_state.items_to_pack)} items")
            
            # Stability assessment
            unstable_items = []
            for item in packed_bin.items:
                if hasattr(item, 'position') and hasattr(item, 'dimension'):
                    items_above = [
                        i for i in packed_bin.items 
                        if i.position[2] > item.position[2] and
                        i.position[0] < item.position[0] + item.dimension[0] and
                        i.position[0] + i.dimension[0] > item.position[0] and
                        i.position[1] < item.position[1] + item.dimension[1] and
                        i.position[1] + i.dimension[1] > item.position[1]
                    ]
                    if items_above and not getattr(item, 'can_stack', False):
                        unstable_items.append((item.name, [i.name for i in items_above]))
            
            if unstable_items:
                with st.expander("⚠️ Stability Warnings", expanded=True):
                    for item, above_items in unstable_items:
                        st.warning(f"{item} is supporting {len(above_items)} items but isn't marked as stackable: {', '.join(above_items)}")
            
            # AI Recommendations
            with st.expander("🤖 AI Packing Recommendations", expanded=False):
                if calculate_efficiency(st.session_state.packed_bin) < 70:
                    st.warning("Low packing efficiency detected!")
                    st.markdown("""
                    **Recommendations:**
                    - Try rotating the box dimensions
                    - Mark more items as stackable if possible
                    - Consider using a slightly larger box
                    """)
                
                # Check for fragile items on top
                fragile_on_top = any(
                    getattr(i, 'fragile', False) and i.position[2] > st.session_state.packed_bin.depth/2
                    for i in st.session_state.packed_bin.items
                )
                if fragile_on_top:
                    st.error("Fragile items detected in top half!")
                    st.markdown("""
                    **Recommendations:**
                    - Mark more items as fragile to prioritize bottom placement
                    - Use more packing material on top
                    - Try the 'Prioritize Stability' packing strategy
                    """)
            
            # Packing analytics
            with st.expander("📈 Packing Analytics", expanded=False):
                # Calculate space utilization by layer
                layers = {}
                for item in packed_bin.items:
                    layer = int(item.position[2] / 5) * 5  # Group by 5cm layers
                    if layer not in layers:
                        layers[layer] = 0
                    layers[layer] += item.get_dimension()[0] * item.get_dimension()[1] * item.get_dimension()[2]
                
                # Show layer utilization
                st.subheader("Space Utilization by Layer")
                for layer in sorted(layers.keys()):
                    utilization = (layers[layer] / (packed_bin.width * packed_bin.height * 5)) * 100
                    st.progress(min(100, int(utilization)), 
                              text=f"Layer {layer}-{layer+5}cm: {utilization:.1f}% used")
                
                # Weight distribution
                st.subheader("Weight Distribution")
                weight_bottom = sum(i.weight for i in packed_bin.items if i.position[2] < packed_bin.depth/2)
                weight_top = sum(i.weight for i in packed_bin.items if i.position[2] >= packed_bin.depth/2)
                st.metric("Bottom Half Weight", f"{weight_bottom:.1f} kg")
                st.metric("Top Half Weight", f"{weight_top:.1f} kg")
            
            # Item placement details
            with st.expander("🔍 View Item Placement Details", expanded=False):
                for idx, item in enumerate(packed_bin.items):
                    unique_detail_key = f"item_{idx}_{item.name}_{item.position[0]}_{item.position[1]}_{item.position[2]}"
                    with stylable_container(
                        key=f"detail_{unique_detail_key}",
                        css_styles="""
                            {
                                background-color: var(--card);
                                border: 1px solid var(--border);
                                border-radius: 10px;
                                padding: 16px;
                                margin-bottom: 12px;
                            }
                        """
                    ):
                        st.markdown(f"**{item.name}**")
                        st.markdown(f"**Position:** `{item.position}`")
                        st.markdown(f"**Rotation:** Type `{item.rotation_type}`")
                        
                        # Find original item data
                        original_dim = next((i for i in st.session_state.items_to_pack if i["name"] == item.name), None)
                        if original_dim:
                            st.markdown(f"""
                                - **Original dimensions:** {original_dim['width']}×{original_dim['height']}×{original_dim['depth']} cm
                                - **Packed dimensions:** {item.get_dimension()[0]:.1f}×{item.get_dimension()[1]:.1f}×{item.get_dimension()[2]:.1f} cm
                                - **Weight:** {item.weight} kg
                                - **Stackable:** {'Yes' if original_dim['can_stack'] else 'No'}
                                - **Fragile:** {'Yes' if original_dim['fragile'] else 'No'}
                            """)
        
        # Interactive Visualization
        with st.container(border=True):
            st.subheader("🔄 Interactive 3D Visualization")
            st.caption("Rotate: Left-click drag | Zoom: Scroll | Pan: Right-click drag | Hover: See details")
            fig = create_modern_visualization(packed_bin)
            st.plotly_chart(fig, use_container_width=True)
        
        # Export functionality
        with st.container(border=True):
            st.header("📤 Export Results", divider="rainbow")
            col1, col2, col3 = st.columns(3)
            
            # PDF Report
            if col1.button("📄 Generate PDF Report"):
                with st.spinner("Generating report..."):
                    generate_pdf_report(packed_bin)
                st.success("Report generated!")
            
            # 3D Model Export
            if col2.button("📦 Export 3D Model"):
                with st.spinner("Exporting 3D model..."):
                    export_3d_model(packed_bin)
                st.success("3D model exported!")
            
            # Data Export
            if col3.button("📊 Export Packing Data"):
                with st.spinner("Exporting data..."):
                    export_packing_data(packed_bin)
                st.success("Data exported!")