export const recipes = [
  { name: 'wafer_defect_detection', type: 'Graph', source: 'User', version: '1.4.2', revision: 12 },
  { name: 'sem_edge_profile', type: 'Linear', source: 'User', version: '1.2.0', revision: 7 },
  { name: 'binary_contour_inspection', type: 'Linear', source: 'Built-in', version: '1.0.0', revision: 1 },
  { name: 'roi_branch_measurement', type: 'Graph', source: 'Built-in', version: '1.0.0', revision: 1 },
];

export const operationGroups = [
  ['Threshold', ['Global Threshold', 'Adaptive Threshold']],
  ['Filtering', ['Gaussian Blur', 'Median Blur', 'Bilateral Filter']],
  ['Morphology', ['Erode', 'Dilate', 'Open / Close']],
  ['Gradient', ['Sobel', 'Canny', 'Laplacian']],
  ['Feature', ['Pixel Statistic', 'Profile Feature', 'Image Similarity']],
  ['Workflow', ['ROI Crop', 'ROI Compose', 'Decision', 'SubRecipe']],
] as const;

export const datasets = [
  { name: 'SEM_Wafer_Test_V3', images: 1240, ok: 965, ng: 275, unlabeled: 0, revision: 9 },
  { name: 'Pattern_Scratch_Set', images: 640, ok: 510, ng: 124, unlabeled: 6, revision: 4 },
  { name: 'Hole_CD_Evaluation', images: 380, ok: 294, ng: 86, unlabeled: 0, revision: 2 },
];

export const evaluations = [
  { id: 'EV-260910-0042', status: 'completed', dataset: 'SEM_Wafer_Test_V3', recipe: 'wafer_defect_detection', progress: 100, accuracy: '98.2%', f1: '97.6%', created: '20:12:44' },
  { id: 'EV-260910-0041', status: 'failed', dataset: 'Pattern_Scratch_Set', recipe: 'sem_edge_profile', progress: 36, accuracy: '-', f1: '-', created: '19:42:11' },
  { id: 'EV-260910-0040', status: 'cancelled', dataset: 'SEM_Wafer_Test_V3', recipe: 'wafer_defect_detection', progress: 71, accuracy: '-', f1: '-', created: '18:17:02' },
  { id: 'EV-260910-0039', status: 'completed', dataset: 'Hole_CD_Evaluation', recipe: 'binary_contour_inspection', progress: 100, accuracy: '96.7%', f1: '95.9%', created: '17:51:28' },
];

export const models = [
  { id: 'wafer_knn', version: '1.0.0', algorithm: 'KNN', labels: 'OK, NG', features: 12 },
  { id: 'pattern_svm', version: '2.1.0', algorithm: 'SVM', labels: 'NORMAL, DEFECT', features: 28 },
];
