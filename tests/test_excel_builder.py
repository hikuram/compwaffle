"""Regression checks for the tested Excel environment compatibility profile.

Run: python -m unittest -v test_builder.py
"""
from __future__ import annotations

import csv
import hashlib
import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from compwaffle import excel as builder


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def csv(self, filename, headers, data):
        path = self.folder / filename
        with path.open('w',encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(data)
        return path

    def test_small_file_import_and_python_formulas(self):
        headers = ['Sample', 'Component A','Component B','Component C','Component D','Metric X','Metric Y']
        data = [['A001',10,20,30,40,1.25,'=HYPERLINK("https://invalid.example","click")'],
                ['A002',25,25,25,25,1.5,'0007'],
                ['A003',1,2,3,4,2.5,'test']]
        path = self.csv('small.csv',headers,data)
        config = replace(builder.Settings(),composition_range='B2:E',
                         evaluation_columns=('F','G'),
                         fill_colors=('#4477AA','#E6A75B','#62AA90','#9966AA'),
                         hatches=('//','..','','/'),
                         evaluation_labels=('Metric One','Metric Two'))
        outfile = self.folder / 'small.xlsx'
        result = builder.build(path,outfile,config)
        self.assertEqual(result['components'],4)
        self.assertEqual(result['draw_rows'],3)
        with ZipFile(outfile) as z:
            self.assertIsNone(z.testzip())
            self.assertIn('xl/media/image1.png', z.namelist())
            self.assertIn('xl/richData/rdrichvalue.xml', z.namelist())
            self.assertNotIn('xl/sharedStrings.xml', z.namelist())
            for name in z.namelist():
                if name.endswith(('.xml','.rels')):
                    etree.fromstring(z.read(name))
            sheet = etree.fromstring(z.read('xl/worksheets/sheet2.xml'))
            source = etree.fromstring(z.read('xl/worksheets/sheet1.xml'))
            ns = {'s':builder.S}
            formulas = {c.get('r'): c.xpath('string(s:f)',namespaces=ns)
                        for c in sheet.xpath('.//s:c[s:f]',namespaces=ns)}
            self.assertEqual(formulas['B3'],'_xlfn._xlws.PY(0,1)')
            self.assertEqual(formulas['B17'],'_xlfn._xlws.PY(1,1)')
            self.assertIn('table!$B2:$E2',formulas['B37'])
            self.assertIn('waffle!$B$4:$B$15',formulas['B37'])
            self.assertIn('waffle!$B$25:$E$25',formulas['B37'])
            self.assertIn('table!$B4:$E4',formulas['B39'])
            self.assertNotIn('B40', formulas)
            self.assertIn('waffle!$B$4:$B$15',formulas['E33'])
            self.assertEqual(formulas['C37'],'table!F2')
            self.assertEqual(formulas['D37'],'table!G2')
            self.assertEqual(formulas['E26'].split('(')[0],'IFERROR')
            self.assertEqual(sheet.xpath('string(.//s:c[@r="D36"]/s:is/s:t)',namespaces=ns),'Metric Two')
            self.assertEqual(sheet.xpath('string(.//s:c[@r="B15"]/s:v)',namespaces=ns),'-30')
            self.assertEqual(source.xpath('string(.//s:c[@r="A2"]/s:is/s:t)',namespaces=ns),'A001')
            self.assertEqual(source.xpath('string(.//s:c[@r="G3"]/s:is/s:t)',namespaces=ns),'0007')
            self.assertTrue(source.xpath('string(.//s:c[@r="G2"]/s:is/s:t)',namespaces=ns).startswith('=HYPERLINK'))
            pfile = etree.fromstring(z.read('xl/python.xml'))
            scripts=pfile.xpath('//*[local-name()="pythonScript"]/*[local-name()="code"]')
            self.assertEqual(len(scripts),4)
            self.assertIn('def cw_draw_row',scripts[1].text)
            self.assertIn('def cw_legend_swatch',scripts[1].text)
            py_cells = sheet.xpath('.//s:c[s:f[starts-with(text(),"_xlfn._xlws.PY")]]',namespaces=ns)
            self.assertTrue(all(c.get('cm')=='1' and c.get('vm') is not None for c in py_cells))
            self.assertTrue(all(c.find(f'{{{builder.S}}}f').get('t')=='array' for c in py_cells))
            self.assertEqual(sheet.xpath('count(.//s:c[@cm="1"])',namespaces=ns),9)
        # Structural read-only third-party interoperability; never save with openpyxl.
        from openpyxl import load_workbook
        w=load_workbook(outfile,read_only=True,data_only=False)
        self.assertEqual(w.sheetnames,['table','waffle'])
        self.assertEqual(w['waffle']['A19'].value,'COMPONENT SETTINGS')
        self.assertTrue(w['waffle']['B37'].value.text.startswith('=_xlfn._xlws.PY'))

    def test_waffle_hint_and_component_alignment(self):
        from openpyxl import load_workbook
        headers = ['Sample'] + [f'C{i}' for i in range(1, 17)]
        path = self.csv('format.csv', headers, [['A'] + [1] * 16])
        cfg = replace(builder.Settings(), composition_range='B2:Q2',
                      evaluation_columns=())
        output = self.folder / 'format.xlsx'
        builder.build(path, output, cfg)
        wb = load_workbook(output, read_only=True)
        ws = wb['waffle']
        # Only D-column setting hints should stop wrapping. Other left-aligned
        # headings and labels keep their original layout.
        for ref in ('D3', 'D4', 'D15', 'D17'):
            self.assertFalse(ws[ref].alignment.wrap_text, ref)
            self.assertEqual(ws[ref].alignment.horizontal, 'left', ref)
        self.assertTrue(ws['A4'].alignment.wrap_text)
        self.assertEqual(ws['B4'].alignment.horizontal, 'general')
        for col in ('B', 'Q'):
            for rn in (20, 21, 22, 23, 24, 25, 26, 28, 32, 33):
                ref = f'{col}{rn}'
                self.assertEqual(ws[ref].alignment.horizontal, 'right', ref)
        self.assertTrue(ws['B20'].alignment.wrap_text)
        self.assertTrue(ws['B32'].alignment.wrap_text)
        self.assertEqual(ws['B37'].alignment.horizontal, 'center')
        self.assertEqual(wb['table']['B1'].alignment.horizontal, 'left')
        wb.close()

    def test_full_16_components_256_rows(self):
        headers=['Sample'] + [f'Component {i:02d}' for i in range(1,17)] + ['Score 1','Score 2','Score 3']
        data=[]
        for i in range(1,257):
            comp=[(j*7+i)%41+1 for j in range(1,17)]
            data.append([f'R{i:04d}']+comp+[i, round(i/3,3),i%7])
        path=self.csv('full.csv',headers,data)
        config=replace(builder.Settings(),composition_range='B2:Q257',
                       evaluation_columns=('R','S','T'))
        outfile=self.folder/'full.xlsx'
        res=builder.build(path,outfile,config)
        self.assertEqual(res['components'],16)
        self.assertEqual(res['draw_rows'],256)
        self.assertEqual(res['python_cells'],274)
        with ZipFile(outfile) as z:
            self.assertIsNone(z.testzip())
            sheet=etree.fromstring(z.read('xl/worksheets/sheet2.xml'))
            ns={'s':builder.S}
            self.assertEqual(sheet.xpath('count(.//s:c[@cm="1"])',namespaces=ns),274)
            last=sheet.xpath('.//s:c[@r="B292"]/s:f',namespaces=ns)[0].text
            self.assertIn('table!$B257:$Q257',last)
            self.assertIn('waffle!$B$25:$Q$25',last)
            self.assertTrue(sheet.xpath('.//s:c[@r="Q33"]/s:f',namespaces=ns))
            self.assertEqual(sheet.xpath('string(.//s:c[@r="Q20"]/s:is/s:t)',namespaces=ns),'Component 16')
            self.assertEqual(len(z.namelist()),20)
            # All visible labels are English, except user-provided CSV content.
            self.assertEqual(sheet.xpath('string(.//s:c[@r="A35"]/s:is/s:t)',namespaces=ns),'COMPOSITION VISUALIZATION')

    def test_bounds_and_invalid_input(self):
        headers=['S'] + [f'C{j}' for j in range(17)]
        p=self.csv('too_many_components.csv',headers,[['1']+[1]*17])
        cfg=replace(builder.Settings(),composition_range='B2:R2',evaluation_columns=())
        with self.assertRaisesRegex(ValueError,'1..16'):
            builder.build(p,self.folder/'bad1.xlsx',cfg)
        data=[[f'R{i}']+[1]*16 for i in range(257)]
        p=self.csv('too_many_rows.csv',['S']+[f'C{j}' for j in range(16)],data)
        cfg=replace(builder.Settings(),composition_range='B2:Q258',evaluation_columns=())
        with self.assertRaisesRegex(ValueError,'1..256'):
            builder.build(p,self.folder/'bad2.xlsx',cfg)
        p=self.csv('negative.csv',['S','C1'],[['A',-1]])
        cfg=replace(builder.Settings(),composition_range='B2:B2',evaluation_columns=())
        with self.assertRaisesRegex(ValueError,'Nonnegative'):
            builder.build(p,self.folder/'bad3.xlsx',cfg)
        p=self.csv('zero.csv',['S','C1'],[['A',0]])
        with self.assertRaisesRegex(ValueError,'zero sum'):
            builder.build(p,self.folder/'bad4.xlsx',cfg)
        p=self.csv('bad_color.csv',['S','C1'],[['A',2]])
        cfg=replace(cfg,fill_colors=('rgb(255,0,0)',))
        with self.assertRaisesRegex(ValueError,'#RRGGBB'):
            builder.build(p,self.folder/'bad5.xlsx',cfg)
        cfg=replace(cfg,fill_colors=('#009999',),hatches=('BAD',))
        with self.assertRaisesRegex(ValueError,'hatch'):
            builder.build(p,self.folder/'bad6.xlsx',cfg)
        cfg=replace(cfg,hatches=('',),options={**builder.OPTIONS,'hatch_tone_shift':101})
        with self.assertRaisesRegex(ValueError,'hatch_tone_shift'):
            builder.build(p,self.folder/'bad7.xlsx',cfg)

    def test_pinned_excel_python_environment_and_formula_metadata(self):
        # Regression guard: this exact initialization was Excel-authored and
        # successfully executed after being restored in diagnostic test A.
        digest='57c24dca0180c0310089ed82fc16aa6baa9c96d8600cc8648cfefc1dfabdb7cb'
        self.assertEqual(hashlib.sha256(builder.PY_ENV_INIT.encode('utf-8')).hexdigest(), digest)
        self.assertEqual(builder.PY_EXCEL_ENVIRONMENT_ID,
                         '{882DD1B0-6546-4DFA-8A08-902A380B44EA}')
        p=self.csv('fixture.csv',['Sample','A','B'],[['001',2,3],['002',3,4]])
        cfg=replace(builder.Settings(),composition_range='B2:C',
                    evaluation_columns=(),fill_colors=('#4477AA','#66A6A0'),
                    hatches=('//',''))
        a=self.folder/'one.xlsx'
        b=self.folder/'two.xlsx'
        builder.build(p,a,cfg)
        builder.build(p,b,cfg)
        py_ns={'p':builder.PY}
        ns={'s':builder.S}
        for path in (a,b):
            with ZipFile(path) as z:
                py=etree.fromstring(z.read('xl/python.xml'))
                env=py.xpath('./p:environmentDefinition',namespaces=py_ns)[0]
                self.assertEqual(env.get('id'),builder.PY_EXCEL_ENVIRONMENT_ID)
                init=py.xpath('./p:environmentDefinition/p:initialization/p:code',
                              namespaces=py_ns)[0]
                self.assertEqual(init.text,builder.PY_ENV_INIT)
                sheet=etree.fromstring(z.read('xl/worksheets/sheet2.xml'))
                pycells=sheet.xpath('.//s:c[s:f[starts-with(text(),"_xlfn._xlws.PY")]]',namespaces=ns)
                self.assertEqual(len(pycells),6)
                self.assertTrue(all(c.get('vm') and c.get('cm')=='1'
                                    and c.find(f'{{{builder.S}}}f').get('ref')==c.get('r')
                                    for c in pycells))
                md=etree.fromstring(z.read('xl/metadata.xml'))
                self.assertEqual(len(md.xpath('//*[local-name()="valueMetadata"]/*[local-name()="bk"]')),
                                 len(pycells)-1)
                self.assertNotIn('xl/embeddings',z.namelist())
        # Pinned environment is identical in independently generated files.
        with ZipFile(a) as za,ZipFile(b) as zb:
            self.assertEqual(za.read('xl/python.xml'),zb.read('xl/python.xml'))

    def test_rgb_hatch_logic(self):
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        env={'np':np}
        exec(builder.PY_ENGINE,env)
        exec(builder.PY_DRAW_FUNCTIONS,env)
        rgb=env['_cw_rgb'](int('4477AA',16))
        self.assertAlmostEqual(env['_cw_tone_rgb'](rgb,-30)[0],rgb[0]*.7)
        count=16
        raw=np.array([i + 1 for i in range(count)],dtype=float)
        colors=np.array([int(c[1:],16) for c in builder.FILL_COLORS])
        shapes=np.full((2,count),np.nan)
        hatches=np.array([2,12]+[0]*14)
        weights=np.array([1]+[0]*15)
        opts=np.array(list(builder.OPTIONS.values()),dtype=float)
        fig=env['cw_draw_row'](raw,colors,shapes,hatches,weights,opts)
        self.assertGreater(len(fig.axes[0].patches),16)
        import matplotlib.pyplot as plt
        plt.close(fig)
        legend=env['cw_legend_swatch'](colors[0],shapes[:,0],hatches[0],opts)
        self.assertEqual(len(legend.axes),1)
        plt.close(legend)


    def test_public_api_aliases_and_cli_custom_ranges(self):
        self.assertIs(builder.ExcelSettings, builder.Settings)
        self.assertIs(builder.build_excel_workbook, builder.build)
        csv_file = self.csv('custom.csv', ['Identifier', 'X', 'Y', 'Other'],
                            [['001', 3, 7, 'note'], ['002', 2, 8, 'text']])
        out = self.folder / 'custom.xlsx'
        from contextlib import redirect_stdout
        import io
        sink = io.StringIO()
        with redirect_stdout(sink):
            exitcode = builder.main([
                str(csv_file), '-o', str(out),
                '--composition-range', 'B2:C3',
                '--sample-id-column', '-',
                '--evaluation-columns', '-',
            ])
        self.assertEqual(exitcode, 0)
        self.assertIn('Visualization: 2 rows, 2 components', sink.getvalue())
        with ZipFile(out) as z:
            sheet = etree.fromstring(z.read('xl/worksheets/sheet2.xml'))
            ns={'s': builder.S}
            self.assertEqual(sheet.xpath('string(.//s:c[@r="A37"]/s:v)',namespaces=ns),'1')
            self.assertEqual(sheet.xpath('count(.//s:c[@r="C37"])',namespaces=ns),0)
            self.assertIn('table!$B2:$C2',sheet.xpath('string(.//s:c[@r="B37"]/s:f)',namespaces=ns))

    def test_generated_sample_matches_tested_excel_profile(self):
        # A canonical artifact created by the user-tested test-A path is
        # reproduced by the package API without any source XLSX template.
        from compwaffle.excel import build_excel_workbook, ExcelSettings
        src = Path(__file__).resolve().parents[1] / 'examples/python_in_excel/example_generic_7.csv'
        expected = Path(__file__).resolve().parents[1] / 'examples/python_in_excel/example_7_components.xlsx'
        out = self.folder / 'roundtrip.xlsx'
        build_excel_workbook(src, out, ExcelSettings())
        with ZipFile(expected) as gold, ZipFile(out) as actual:
            self.assertEqual(gold.namelist(), actual.namelist())
            for name in gold.namelist():
                self.assertEqual(gold.read(name), actual.read(name), f'OOXML mismatch: {name}')


if __name__=='__main__':
    unittest.main(verbosity=2)
