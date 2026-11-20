Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$p = Get-Process lceda-pro | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 1
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[Win32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 800
$r = New-Object Win32+RECT
[Win32]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
$bmp.Save("D:\Document\tempPrj\74Series-CNN\tools\b02_work\b02_screen.png")
Write-Output "saved ${w}x${h}"
