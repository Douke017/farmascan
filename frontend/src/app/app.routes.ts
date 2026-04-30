import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/scanner/scanner.component').then((m) => m.ScannerComponent),
    title: 'FarmaScan — Escanear LPN',
  },
  {
    path: 'upload',
    loadComponent: () =>
      import('./features/upload/upload.component').then((m) => m.UploadComponent),
    title: 'FarmaScan — Cargar inventario',
  },
  { path: '**', redirectTo: '' },
];
