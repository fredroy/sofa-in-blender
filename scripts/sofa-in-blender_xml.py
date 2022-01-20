#! python3
import os
# define here the env. variable for SOFA_ROOT and SOFAPYTHON3_ROOT if not already defined system-wide
# os.environ["SOFA_ROOT"] = XXXXXX
# os.environ["SOFAPYTHON3_ROOT"] = XXXXX


import Sofa
from SofaRuntime import Timer

import bpy

# SOFA+Blender
def get_visual_models(node):
    local_list_visual_model = []
    for obj in node.objects: 
        if obj.getData("vertices") and (obj.getData("triangles") or obj.getData("quads")):
            # could filter also with "VisualModel" in obj.getCategories() :
            # but seems unreliable?
            local_list_visual_model.append(obj)
            
    return local_list_visual_model

def build_collection_tree(node, root_collection, dict_visual_models):
    for child in node.children:
        new_collection = bpy.data.collections.new(child.name.value)
        root_collection.children.link(new_collection)
        local_list_visual_model = get_visual_models(child)
        if local_list_visual_model:
            for visual_model in local_list_visual_model:
                new_mesh = bpy.data.meshes.new(visual_model.name.value)
                # make object from mesh
                new_object = bpy.data.objects.new(visual_model.name.value + '_object', new_mesh)
                # add object to scene collection
                new_collection.objects.link(new_object)
                dict_visual_models[visual_model] = new_object
                # fill
                vertices = []
                edges = []
                faces = []
#                print(f"Vertices size: {visual_model.position.array().size}")
#                print(f"Edges size: {visual_model.edges.array().size}")
#                print(f"Triangles size: {visual_model.triangles.array().size}")
#                print(f"Quads size: {visual_model.quads.array().size}")
                for v in visual_model.position.array():
                    newv = (v[0], v[1], v[2])
                    vertices.append(newv)
                for e in visual_model.edges.array():
                    newe = (e[0], e[1])
                    edges.append(newe)
                for t in visual_model.triangles.array():
                    newt = [t[0], t[1], t[2]]
                    faces.append(newt)
                for q in visual_model.quads.array():
                    newq = [q[0], q[1], q[2], q[3]]
                    faces.append(newq)
                # create
                new_mesh.clear_geometry()
                new_mesh.from_pydata(vertices, edges, faces)
                new_mesh.update()
        build_collection_tree(child, new_collection, dict_visual_models)

# SOFA
def createScene(root):
    test_xml_scene= os.environ['SOFA_ROOT']  + "\\share\\sofa\\examples\\Demos\\" + 'liver.scn'
    loaded_node = Sofa.Simulation.load(test_xml_scene)
    root.addChild(loaded_node)


# When not using runSofa, this main function will be called python
def main():
    sofa_collection_name = 'SOFA_Collection'
    number_of_frames = 100
    number_of_sofa_iterations = 1000
    increment_each_sofa_iteration = number_of_frames / number_of_sofa_iterations

    if bpy.data.collections.find(sofa_collection_name) >= 0:
        previous_sofa_collection = bpy.data.collections.get(sofa_collection_name)
        for obj in previous_sofa_collection.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(previous_sofa_collection)
        for c in bpy.data.collections:
            if not c.users:
                bpy.data.collections.remove(c)
        for o in bpy.data.objects:
            if not o.users:
                bpy.data.objects.remove(o)

    sofa_collection = bpy.data.collections.new('SOFA_Collection')
    bpy.context.scene.collection.children.link(sofa_collection)

    root = Sofa.Core.Node("root")
    createScene(root)
    Sofa.Simulation.init(root)

    dict_visual_models = {}
    build_collection_tree(root, sofa_collection, dict_visual_models)
    
    if not dict_visual_models.items():
        print("No (compatible) Visual Model detected...")

    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = number_of_frames

    current_frame = 0
    total_increment = 0
    for current_sofa_iteration in range(1, number_of_sofa_iterations):
        print(f'Sofa Iteration #{current_sofa_iteration}')
        Sofa.Simulation.animate(root, root.dt.value)

        total_increment += increment_each_sofa_iteration
        if total_increment < current_frame:
            continue
        
        current_frame += 1
        print(f'Blender frame #{current_frame}')
        for key, value in dict_visual_models.items():
            sofa_visual_model = key
            blender_visual_model = value
            bvindex = 0
            for sv in sofa_visual_model.position.array():
                blender_visual_model.data.vertices[bvindex].co = [sv[0], sv[1], sv[2]]
                blender_visual_model.data.vertices[bvindex].keyframe_insert("co", frame=current_frame)
                bvindex = bvindex+1


if __name__ == '__main__':
    main()
