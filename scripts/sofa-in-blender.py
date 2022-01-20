#! python3
import os
# define here the env. variable for SOFA_ROOT and SOFAPYTHON3_ROOT if not already defined system-wide
# os.environ["SOFA_ROOT"] = XXXXXX
# os.environ["SOFAPYTHON3_ROOT"] = XXXXX

import Sofa
from SofaRuntime import Timer

import bpy

# This controller will extract the timer records from the simulation at each steps
class TimerController(Sofa.Core.Controller):

    def __init__(self, *args, **kwargs):
        Sofa.Core.Controller.__init__(self, *args, **kwargs)

        # This is needed to avoid a conflict with the timer of runSofa
        self.use_sofa_profiler_timer = False

    def onAnimateBeginEvent(self, event):
        if len(Timer.getRecords('Animate')):
            self.use_sofa_profiler_timer = True
        else:
            Timer.setEnabled("cg_timer", True)
            Timer.begin("cg_timer")

    def onAnimateEndEvent(self, event):
        if self.use_sofa_profiler_timer:
            records = Timer.getRecords("Animate")
        else:
            records = Timer.getRecords("cg_timer")

        step_time = records['AnimateVisitor']['Mechanical (meca)']['total_time']
        print(f"Step took {step_time:.2f} ms")

        nb_iterations = records['AnimateVisitor']['Mechanical (meca)']['StaticSolver::Solve']['nb_iterations']
        for i in range(int(nb_iterations)):
            total_time = records['AnimateVisitor']['Mechanical (meca)']['StaticSolver::Solve']['NewtonStep'][i]['total_time']
            CG_iterations = records['AnimateVisitor']['Mechanical (meca)']['StaticSolver::Solve']['NewtonStep'][i]['MBKSolve']['CG iterations']
            print(f"  Newton iteration #{i} took {total_time:.2f} ms using {int(CG_iterations)} CG iterations")

        if not self.use_sofa_profiler_timer:
            Timer.end("cg_timer")


# Scene creation - This is automatically called by SofaPython3 when using runSofa
def createScene(root):
    root.dt = 0.01

    # List of required plugins
    root.addObject('RequiredPlugin', name='SofaBaseMechanics')
    root.addObject('RequiredPlugin', name='SofaSparseSolver')
    root.addObject('RequiredPlugin', name='SofaGraphComponent')
    root.addObject('RequiredPlugin', name='SofaPreconditioner')
    root.addObject('RequiredPlugin', name='SofaBoundaryCondition')
    root.addObject('RequiredPlugin', name='SofaEngine')
    root.addObject('RequiredPlugin', name='SofaImplicitOdeSolver')
    root.addObject('RequiredPlugin', name='SofaSimpleFem')

    # Visual style
    root.addObject('VisualStyle', displayFlags='showBehaviorModels showForceFields')

    # Add the python controller in the scene
    root.addObject( TimerController() )

    # Create a grid topology of 10x10x60 centered on (0,0,0)
    root.addObject('RegularGridTopology', name='grid', min=[-5, -5, -30], max=[5, 5, 30], n=[11, 11, 61])

    # Create our mechanical node
    root.addChild("meca")
    root.meca.addObject("StaticSolver", newton_iterations=5, printLog=False)
    root.meca.addObject("CGLinearSolver")

    root.meca.addObject('MechanicalObject', name='mo', position='@../grid.position')
    root.meca.addObject('HexahedronSetTopologyContainer', name='mechanical_topology', src='@../grid')
    root.meca.addObject('HexahedronFEMForceField', youngModulus=3000, poissonRatio=0)

    root.meca.addObject('BoxROI', name='base_roi', box=[-5.01, -5.01, -30.01, 30.01, 30.01, -29.99])
    root.meca.addObject('BoxROI', name='top_roi',  box=[-5.01, -5.01, +29.99, 5.01, 5.01, +30.01], quad='@mechanical_topology.quads')

    root.meca.addObject('FixedConstraint', indices='@base_roi.indices')
    root.meca.addObject('QuadSetGeometryAlgorithms')
    root.meca.addObject('QuadPressureForceField', pressure=[0, -30, 0], quadList='@top_roi.quadInROI', showForces=False)

    # Create visual mapped node
    root.meca.addChild("visu")
    root.meca.visu.addObject("VisualModelImpl", name="model")
    root.meca.visu.addObject("IdentityMapping")

def get_visual_models(node):
    local_list_visual_model = []
    for obj in node.objects:
        if "VisualModel" in obj.getCategories() :
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
                for v in visual_model.position.array():
                    newv = (v[0], v[1], v[2])
                    vertices.append(newv)
                for e in visual_model.edges.array():
                    newe = (e[0], e[1])
                    edges.append(newe)
                for q in visual_model.quads.array():
                    newq = [q[0], q[1], q[2], q[3]]
                    faces.append(newq)
                # create
                new_mesh.clear_geometry()
                new_mesh.from_pydata(vertices, edges, faces)
                new_mesh.update()
        build_collection_tree(child, new_collection, dict_visual_models)


# When not using runSofa, this main function will be called python
def main():
    sofa_collection_name = 'SOFA_Collection'
    number_of_frames = 50

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

    # Run the simulation for number_of_frames steps
    for iteration in range(1, number_of_frames):
        print(f'Iteration #{iteration}')
        Sofa.Simulation.animate(root, root.dt.value)

        for key, value in dict_visual_models.items():
            sofa_visual_model = key
            blender_visual_model = value
            bvindex = 0
            for sv in sofa_visual_model.position.array():
                blender_visual_model.data.vertices[bvindex].co = [sv[0], sv[1], sv[2]]
                blender_visual_model.data.vertices[bvindex].keyframe_insert("co", frame=iteration)
                bvindex = bvindex+1


if __name__ == '__main__':
    main()
