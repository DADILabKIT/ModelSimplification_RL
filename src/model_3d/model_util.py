from abc import ABC, abstractmethod
from multipledispatch import dispatch
from typing import List
from pytorch3d import loss
from pytorch3d.loss.point_mesh_distance import point_mesh_face_distance
from pytorch3d.structures import Pointclouds, Meshes

from src.model_3d.cad_model import MetaModel, Assembly, PartModel



class Evaluator(ABC):
    def __init__(self) -> None:
        super().__init__()  
    
    
    @abstractmethod
    def evaluate(self, model: MetaModel) -> float:
        pass    

class ChamferDistance(Evaluator):
    def __init__(self) -> None:
        super().__init__()  
        
    @dispatch(PartModel, PartModel)
    def evaluate(self, 
                model: PartModel, 
                other_model: PartModel) -> float:
    
        
        p1: Pointclouds = model.torch_point_cloud
        p2: Pointclouds = other_model.torch_point_cloud
        
        chamfer_distance_loss, loss_normal = loss.chamfer_distance(p1, p2, 
                                                        point_reduction="mean", 
                                                        single_directional=False)
        
        return chamfer_distance_loss.item()
    @dispatch(Meshes, Meshes)   
    def evaluate(self,
                mesh: Meshes, 
                other_mesh: Meshes) -> float:
        
            chamfer_distance_loss, loss_normal = loss.chamfer_distance(mesh, other_mesh, 
                                                            point_reduction="mean", 
                                                            single_directional=False)
            
            return chamfer_distance_loss.item() 
        
    @dispatch(Pointclouds, Pointclouds)
    def evaluate(self,
                point_cloud: Pointclouds, 
                other_point_cloud: Pointclouds) -> float:
        
            chamfer_distance_loss, loss_normal = loss.chamfer_distance(point_cloud, other_point_cloud, 
                                                            point_reduction="mean", 
                                                            single_directional=False)
            
            return chamfer_distance_loss.item() 
        
    @dispatch(Assembly, Assembly)
    def evaluate(self,
                assembly: Assembly,
                other_assembly: Assembly) -> float:
        
        if len(assembly.part_model_list) != len(other_assembly.part_model_list):
            raise ValueError("assembly and other_assembly must have same length")
        sum_of_chamfer_distance: float = 0.0
        for part_index in range(len(assembly.part_model_list)):
            part_model = assembly.part_model_list[part_index]
            other_part_model = other_assembly.part_model_list[part_index]
            
            chamfer_distance = self.evaluate(part_model, other_part_model)
            
            sum_of_chamfer_distance += chamfer_distance 
        return sum_of_chamfer_distance
        
class PointToMeshDistance(Evaluator):   
    def __init__(self) -> None:
        super().__init__()
        
    def evaluate(self, model: PartModel, other_model: PartModel) -> float:
        pmd1 = point_mesh_face_distance(
            model.torch_mesh, 
            other_model.torch_point_cloud).item()
        
        pmd2 = point_mesh_face_distance(
            other_model.torch_mesh, 
            model.torch_point_cloud).item()  
        
        return (pmd1 + pmd2) * 0.5


class Cluster(ABC):
    def __init__(self) -> None:
        super().__init__()  
        
        
    @abstractmethod
    def cluster(self, assembly: Assembly) -> List[List[int]]:
        pass    
    
class RegionGrowing(Cluster):
    def __init__(self, growing_ratio: float = 0.5) -> None:
        super().__init__()  
        self.growing_ratio: float = growing_ratio  
        self.closed_list: List[int] = []    
        self.cluster_list: List[List[int]] = []
        
        
    def cluster(self, assembly: Assembly) -> List[List[int]]:
        cluster: List[int] = []
        if assembly.part_model_list is None:    
            raise ValueError("assembly.part_model_list must not be None")   
        if len(assembly.part_model_list) == 1 or len(assembly.part_model_list) == 0 or len(assembly.conectivity_dict) == 0:
            cluster.append(0)
            self.cluster_list.append(cluster)
            return self.cluster_list    
            

        for part_model in assembly.part_model_list:
            part_index: int = part_model.part_index    
            seed_volume: float = assembly.part_model_list[part_index].get_volume()
            self.growing(part_index, assembly, cluster, seed_volume)
            
            if len(cluster) == 0:   
                continue
            
            input_list = []
            input_list.extend(cluster)
            self.cluster_list.append(input_list)
            cluster.clear() 
            
        self.set_part_model_color(assembly)
        return self.cluster_list
    
    def growing(self, 
                part_index: int, 
                assembly: Assembly, 
                cluster: List[int], 
                seed_number: float) -> None:
        if part_index in self.closed_list:  
            return None 
        
        cluster.append(part_index)
        self.closed_list.append(part_index)
        neighbor_index_list: list[int] = assembly.conectivity_dict[part_index]

        for neighbor_index in neighbor_index_list:
            neighbor_part: PartModel = assembly.part_model_list[neighbor_index]    
            
            if self.growing_ratio * neighbor_part.get_volume() < seed_number:
                continue
            
            self.growing(neighbor_index, assembly, cluster, seed_number)
        
        return None
    
    def set_part_model_color(self, assembly: Assembly) -> None:
        colors = ["red", "blue", "yellow", "purple", "green", "orange", "pink", "brown", "gray", "black"]
        for cluster_index, cluster in enumerate(self.cluster_list):
            cluster_index = cluster_index % len(colors) 
            for part_index in cluster:
                assembly.part_model_list[part_index].color = colors[cluster_index]    
        return None
    