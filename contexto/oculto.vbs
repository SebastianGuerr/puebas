' Lanza un .cmd SIN VENTANA y devuelve su codigo de salida (contexto\docs\CONTEXTO_EXTERNO.md).
' La tarea vieja murio el 2026-10-13 porque se cerro su ventana negra de cmd (calendarios\docs\CAPTURAS.md):
' con wscript y estilo de ventana 0 no hay consola que cerrar.
'     wscript.exe //B //NoLogo oculto.vbs <archivo.cmd> [argumentos...]
' Una ruta relativa se busca primero en la carpeta actual y luego junto a este .vbs.
' Codigos: el del .cmd; 2 si no se paso un .cmd o no existe.
Option Explicit
Dim sh, fso, aqui, cmd, args, i, a, codigo
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 0 Then WScript.Quit 2
aqui = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = WScript.Arguments(0)
If Not fso.FileExists(cmd) Then cmd = fso.BuildPath(aqui, cmd)
If Not fso.FileExists(cmd) Then WScript.Quit 2
cmd = fso.GetAbsolutePathName(cmd)
args = ""
For i = 1 To WScript.Arguments.Count - 1
    a = WScript.Arguments(i)
    If InStr(a, " ") > 0 Then a = """" & a & """"
    args = args & " " & a
Next
' cmd /c ""ruta" args": cmd quita las comillas de fuera y respeta las de la ruta
codigo = sh.Run("%ComSpec% /d /c """"" & cmd & """" & args & """", 0, True)
WScript.Quit codigo
