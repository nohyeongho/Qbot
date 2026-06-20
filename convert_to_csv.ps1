$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open("d:\app_github\04_Dashboard_Qbot\RawData_202605_v1.xlsx")
$wb.SaveAs("d:\app_github\04_Dashboard_Qbot\RawData_202605_v1.csv", 6)
$wb.Close($false)
$excel.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
