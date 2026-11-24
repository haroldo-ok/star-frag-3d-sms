; Star Frag 3D - ray casting and view composition for two side-by-side views (Z80)
;
; Rays 0..31 are player 1's view (screen x 0..127), rays 32..63 player 2's.
; cast_rays casts the 32 rays starting at ray_base from (px,py,pa);
; draw_view draws the 16 tile columns starting at dv_first.
;
; cast_rays:  Even rays (and the last) are cast with a DDA whose inner
; loop runs from RAM with its step constants patched per ray; an odd ray whose
; two neighbours hit the same face of the same cell is interpolated instead.
;
; draw_view: per tile column, compares the two rays with what is on screen,
; builds the top half of the column (draw_left/draw_right), uploads it
; (out_column) and switches the name-table cells between the shared sky tile
; and the column tile.  The bottom half of the view is the vertical mirror:
; same tile, V-flip bit + sprite palette (floor colours).

	.module ray
	.include "gen/assets.inc"

VIEW_BASE = 64
dda_ram   = 0xD6C0
SKY_BASE  = 48
NT_TOP    = 0x7880          ; name table address of view cell (0,2), write flag set
NT_BOT    = 0x7B40          ; ... of cell (0,13)

	.globl _pa, _px, _py, _map, _zbuf, _cosoff, _rayoff
	.globl _rd_bank, _rd_l, _rd_y0, _rd_rows, _rd_vaddr
	.globl _draw_left, _draw_right, _out_column, _mul8, _oc_tc

	.area _DATA
_ray::		.ds 256		; 64 x {k, l, bank, side}
_ray_hit::	.ds 128		; 64 x hit cell pointer
_sig::		.ds 256		; what is on screen (same layout as _ray)
_nt_state::	.ds 192		; 32 x 6: 0 sky / 1 wall tile
_ray_base::	.ds 1
_dv_first::	.ds 1
cr_n:		.ds 1
nt_hi:		.ds 1
dv_end:		.ds 1
;dda_ram is at a fixed address (0xD6C0, below COLBUF)
cr_i:		.ds 1
cr_ddx:		.ds 2
cr_ddy:		.ds 2
cr_ca:		.ds 1
cr_sa:		.ds 1
cr_fl:		.ds 1
cr_sdx:		.ds 2
cr_dist:	.ds 2
cr_side:	.ds 1
cr_hit:		.ds 2
cr_u:		.ds 1
cr_p0:		.ds 2
t_k1:		.ds 1
t_l1:		.ds 1
t_b1:		.ds 1
t_s1:		.ds 1
t_k2:		.ds 1
t_l2:		.ds 1
t_cur:		.ds 2
dv_tc:		.ds 1
dv_r0:		.ds 1
dv_rp:		.ds 2

	.area _CODE

; ---------------------------------------------------------------- DDA (copied to RAM)
; in: HL = side dist x, DE = side dist y, BC = map pointer
; out: HL = distance, A = side (0 x-face, 1 y-face), BC = hit cell pointer
dda_tpl:
d_loop:
	ld	a,l
	sub	e
	ld	a,h
	sbc	a,d
	jr	nc,d_y
d_xmap:
	inc	bc			; patched: inc bc / dec bc
	ld	a,(bc)
	or	a
	jr	nz,d_hitx
	ld	a,l
	add	a,#0
d_xlo = . - 1
	ld	l,a
	ld	a,h
	adc	a,#0
d_xhi = . - 1
	ld	h,a
	jr	d_loop
d_y:
	ld	a,c
	add	a,#0
d_ylo = . - 1
	ld	c,a
	ld	a,b
	adc	a,#0
d_yhi = . - 1
	ld	b,a
	ld	a,(bc)
	or	a
	jr	nz,d_hity
	ld	a,e
	add	a,#0
d_dlo = . - 1
	ld	e,a
	ld	a,d
	adc	a,#0
d_dhi = . - 1
	ld	d,a
	jr	d_loop
d_hitx:
	xor	a
	ret
d_hity:
	ex	de,hl
	ld	a,#1
	ret
dda_end:

_ray_init::
	ld	hl,#dda_tpl
	ld	de,#dda_ram
	ld	bc,#dda_end - dda_tpl
	ldir
	ret

; ---------------------------------------------------------------- one ray
; A = ray index
cast_one:
	ld	(cr_i),a
	and	#31
	ld	e,a
	ld	d,#0
	ld	hl,#_rayoff
	add	hl,de
	ld	a,(hl)
	ld	e,a
	rla
	sbc	a,a
	ld	d,a
	ld	hl,(_pa)
	add	hl,de
	ld	a,h
	and	#3
	ld	h,a
	add	hl,hl
	add	hl,hl
	add	hl,hl
	set	7,h			; angle record at 0x8000 + a*8
	ld	e,(hl)
	inc	hl
	ld	d,(hl)
	inc	hl
	ld	(cr_ddx),de
	ld	a,e
	ld	(dda_ram + d_xlo - dda_tpl),a
	ld	a,d
	ld	(dda_ram + d_xhi - dda_tpl),a
	ld	e,(hl)
	inc	hl
	ld	d,(hl)
	inc	hl
	ld	(cr_ddy),de
	ld	a,e
	ld	(dda_ram + d_dlo - dda_tpl),a
	ld	a,d
	ld	(dda_ram + d_dhi - dda_tpl),a
	ld	a,(hl)
	ld	(cr_ca),a
	inc	hl
	ld	a,(hl)
	ld	(cr_sa),a
	inc	hl
	ld	a,(hl)
	ld	(cr_fl),a
	; ---- x
	rra				; carry = cos < 0
	ld	a,(_px)
	ld	de,(cr_ddx)
	jr	c,1$
	ld	b,a
	ld	a,#0x03			; inc bc
	ld	(dda_ram + d_xmap - dda_tpl),a
	ld	a,b
	or	a
	jr	z,2$			; on a boundary: a whole cell
	neg
	call	_mul8
	jr	2$
1$:	ld	b,a
	ld	a,#0x0B			; dec bc
	ld	(dda_ram + d_xmap - dda_tpl),a
	ld	a,b
	call	_mul8
2$:	ld	(cr_sdx),de
	; ---- y
	ld	a,(cr_fl)
	and	#2
	ld	a,(_py)
	ld	de,(cr_ddy)
	jr	nz,3$
	ld	b,a
	ld	a,#32
	ld	(dda_ram + d_ylo - dda_tpl),a
	xor	a
	ld	(dda_ram + d_yhi - dda_tpl),a
	ld	a,b
	or	a
	jr	z,4$
	neg
	call	_mul8
	jr	4$
3$:	ld	b,a
	ld	a,#0xE0
	ld	(dda_ram + d_ylo - dda_tpl),a
	ld	a,#0xFF
	ld	(dda_ram + d_yhi - dda_tpl),a
	ld	a,b
	call	_mul8
4$:	ld	hl,(cr_sdx)
	ld	bc,(cr_p0)
	call	dda_ram
	ld	(cr_dist),hl
	ld	(cr_side),a
	ld	(cr_hit),bc
	; ---- texture column u
	or	a
	jr	nz,6$
	ld	a,(cr_sa)		; x face: along y
	ld	de,(cr_dist)
	call	_mul8
	ld	a,(cr_fl)
	and	#2
	ld	a,(_py)
	jr	nz,5$
	add	a,e
	jr	51$
5$:	sub	e
51$:	rrca
	rrca
	rrca
	and	#31
	ld	b,a
	ld	a,(cr_fl)
	rra
	ld	a,b
	jr	nc,8$
	cpl
	and	#31
	jr	8$
6$:	ld	a,(cr_ca)		; y face: along x
	ld	de,(cr_dist)
	call	_mul8
	ld	a,(cr_fl)
	rra
	ld	a,(_px)
	jr	c,7$
	add	a,e
	jr	71$
7$:	sub	e
71$:	rrca
	rrca
	rrca
	and	#31
	ld	b,a
	ld	a,(cr_fl)
	and	#2
	ld	a,b
	jr	nz,8$
	cpl
	and	#31
8$:	ld	(cr_u),a
	; ---- perpendicular distance, depth buffer, row-table index
	ld	a,(cr_i)
	and	#31
	ld	e,a
	ld	d,#0
	ld	hl,#_cosoff
	add	hl,de
	ld	a,(hl)
	ld	de,(cr_dist)
	call	_mul8
	ld	a,d
	or	a
	jr	nz,9$
	ld	a,e
	cp	#80
	jr	nc,9$
	ld	e,#80
9$:	ld	a,(cr_i)
	ld	l,a
	ld	h,#0
	add	hl,hl
	ld	bc,#_zbuf
	add	hl,bc
	ld	(hl),e
	inc	hl
	ld	(hl),d
	ex	de,hl
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	ld	a,h
	cp	#6
	jr	c,10$
	ld	hl,#0x5FF
10$:	ld	bc,#0xA000
	add	hl,bc
	ld	c,(hl)			; k
	ld	a,(cr_i)
	add	a,a
	add	a,a
	ld	e,a
	ld	d,#0
	ld	hl,#_ray
	add	hl,de
	ld	(hl),c
	inc	hl
	ex	de,hl
	ld	hl,(cr_hit)
	ld	a,(hl)
	dec	a
	add	a,a
	ld	b,a
	ld	a,(cr_side)
	add	a,b			; texture variant v
	ld	b,a
	and	#7
	rrca
	rrca
	rrca
	ld	c,a
	ld	a,(cr_u)
	or	c
	ex	de,hl
	ld	(hl),a			; l
	inc	hl
	ld	a,b
	rrca
	rrca
	rrca
	and	#0x1F
	add	a,#TEXBANK0
	ld	(hl),a			; bank
	inc	hl
	ld	a,(cr_side)
	ld	(hl),a
	ld	a,(cr_i)
	ld	l,a
	ld	h,#0
	add	hl,hl
	ld	de,#_ray_hit
	add	hl,de
	ld	de,(cr_hit)
	ld	(hl),e
	inc	hl
	ld	(hl),d
	ret

; A = odd ray index: interpolate between its neighbours when they hit the
; same face of the same cell, else cast it
interp_one:
	ld	(cr_i),a
	ld	l,a
	ld	h,#0
	add	hl,hl
	ld	de,#_ray_hit - 2
	add	hl,de
	ld	e,(hl)
	inc	hl
	ld	d,(hl)
	inc	hl
	inc	hl
	inc	hl
	ld	a,(hl)
	cp	e
	jp	nz,i_cast
	inc	hl
	ld	a,(hl)
	cp	d
	jp	nz,i_cast
	ld	a,(cr_i)
	add	a,a
	add	a,a
	ld	e,a
	ld	d,#0
	ld	hl,#_ray - 4
	add	hl,de
	ld	a,(hl)
	ld	(t_k1),a
	inc	hl
	ld	a,(hl)
	ld	(t_l1),a
	inc	hl
	ld	a,(hl)
	ld	(t_b1),a
	inc	hl
	ld	a,(hl)
	ld	(t_s1),a
	inc	hl
	ld	(t_cur),hl
	inc	hl
	inc	hl
	inc	hl
	inc	hl
	ld	a,(hl)
	ld	(t_k2),a
	inc	hl
	ld	a,(hl)
	ld	(t_l2),a
	inc	hl
	inc	hl
	ld	a,(t_s1)
	cp	(hl)
	jp	nz,i_cast
	ld	hl,(t_cur)
	ld	a,(t_k1)
	ld	b,a
	ld	a,(t_k2)
	add	a,b
	rra
	ld	(hl),a
	inc	hl
	ld	a,(t_l1)
	and	#31
	ld	b,a
	ld	a,(t_l2)
	and	#31
	add	a,b
	rra
	ld	b,a
	ld	a,(t_l1)
	and	#0xE0
	or	b
	ld	(hl),a
	inc	hl
	ld	a,(t_b1)
	ld	(hl),a
	inc	hl
	ld	a,(t_s1)
	ld	(hl),a
	; hit pointer = neighbour's, depth = average
	ld	a,(cr_i)
	ld	l,a
	ld	h,#0
	add	hl,hl
	push	hl
	ld	de,#_ray_hit - 2
	add	hl,de
	ld	e,(hl)
	inc	hl
	ld	d,(hl)
	inc	hl
	ld	(hl),e
	inc	hl
	ld	(hl),d
	pop	hl
	ld	de,#_zbuf - 2
	add	hl,de
	ld	e,(hl)
	inc	hl
	ld	d,(hl)
	inc	hl
	push	hl
	inc	hl
	inc	hl
	ld	a,(hl)
	inc	hl
	ld	h,(hl)
	ld	l,a
	add	hl,de
	rr	h
	rr	l
	ex	de,hl
	pop	hl
	ld	(hl),e
	inc	hl
	ld	(hl),d
	ret
i_cast:
	ld	a,(cr_i)
	jp	cast_one

_cast_rays::
	ld	a,#ANG_BANK
	ld	(0xFFFF),a
	ld	a,(_py + 1)
	ld	l,a
	ld	h,#0
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	ld	a,(_px + 1)
	or	l
	ld	l,a
	ld	de,#_map
	add	hl,de
	ld	(cr_p0),hl
	ld	a,(_ray_base)
	ld	(cr_n),a
	ld	b,#16
11$:	push	bc
	ld	a,(cr_n)
	call	cast_one
	ld	a,(cr_n)
	add	a,#2
	ld	(cr_n),a
	pop	bc
	djnz	11$
	ld	a,(_ray_base)
	add	a,#31
	call	cast_one
	ld	a,(_ray_base)
	inc	a
	ld	(cr_n),a
	ld	b,#15
12$:	push	bc
	ld	a,(cr_n)
	call	interp_one
	ld	a,(cr_n)
	add	a,#2
	ld	(cr_n),a
	pop	bc
	djnz	12$
	ret

; ---------------------------------------------------------------- the view
; A = k -> rd_rows = ROWS_BASE + k*48 (preserves HL)
rows_ptr:
	push	hl
	ld	l,a
	ld	h,#0
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,de
	ld	de,#ROWS_BASE
	add	hl,de
	ld	(_rd_rows),hl
	pop	hl
	ret

; HL = name table address (write flag set), A = tile low, C = high byte
nt_write:
	ld	b,a
	di
	ld	a,l
	out	(0xBF),a
	ld	a,h
	out	(0xBF),a
	ei
	ld	a,b
	out	(0xBE),a
	ld	a,c
	nop
	nop
	nop
	out	(0xBE),a
	ret

_draw_view::
	ld	a,(_dv_first)
	ld	(dv_tc),a
	add	a,#16
	ld	(dv_end),a
dv_loop:
	ld	a,(dv_tc)
	add	a,a
	add	a,a
	add	a,a
	ld	c,a
	ld	b,#0
	ld	hl,#_ray
	add	hl,bc
	ld	(dv_rp),hl
	ld	hl,#_sig
	add	hl,bc
	ex	de,hl
	ld	hl,(dv_rp)
	ld	b,#8
20$:	ld	a,(de)
	cp	(hl)
	jr	nz,21$
	inc	hl
	inc	de
	djnz	20$
	jp	dv_next
21$:	ld	a,(dv_tc)
	add	a,a
	add	a,a
	add	a,a
	ld	e,a
	ld	d,#0
	ld	hl,#_sig
	add	hl,de
	ex	de,hl
	ld	hl,(dv_rp)
	ld	bc,#8
	ldir
	; first row that holds wall pixels in this column
	ld	hl,(dv_rp)
	ld	a,(hl)
	cp	#48
	jr	c,22$
	xor	a
	jr	23$
22$:	neg
	add	a,#48
23$:	ld	b,a
	inc	hl
	inc	hl
	inc	hl
	inc	hl
	ld	a,(hl)
	cp	#48
	jr	c,24$
	xor	a
	jr	25$
24$:	neg
	add	a,#48
25$:	cp	b
	jr	c,26$
	ld	a,b
26$:	and	#0xF8
	ld	(_rd_y0),a
	rrca
	rrca
	rrca
	ld	(dv_r0),a
	cp	#6
	jr	nc,dv_nt
	ld	hl,(dv_rp)
	ld	a,(hl)
	call	rows_ptr
	inc	hl
	ld	a,(hl)
	ld	(_rd_l),a
	inc	hl
	ld	a,(hl)
	ld	(_rd_bank),a
	call	_draw_left
	ld	hl,(dv_rp)
	ld	de,#4
	add	hl,de
	ld	a,(hl)
	call	rows_ptr
	inc	hl
	ld	a,(hl)
	ld	(_rd_l),a
	inc	hl
	ld	a,(hl)
	ld	(_rd_bank),a
	call	_draw_right
	ld	a,(dv_tc)
	ld	b,a
	add	a,a
	add	a,b
	add	a,a
	ld	b,a
	ld	a,(dv_r0)
	add	a,b
	add	a,#VIEW_BASE
	ld	l,a
	ld	h,#0
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	set	6,h
	ld	(_rd_vaddr),hl
	ld	a,(dv_tc)
	ld	(_oc_tc),a
	call	_out_column
dv_nt:
	; name-table cells: rows < r0 -> sky tile, rows >= r0 -> column tile
	ld	a,(dv_tc)
	ld	b,a
	add	a,a
	add	a,b
	add	a,a			; tc*6
	ld	e,a
	ld	d,#0
	ld	hl,#_nt_state
	add	hl,de
	ld	b,#0			; r
30$:	ld	a,(dv_r0)
	ld	c,a
	ld	a,b
	sub	c			; carry if r < r0
	ccf
	ld	a,#0
	rla				; want = r >= r0
	cp	(hl)
	jr	z,31$
	ld	(hl),a
	push	hl
	push	bc
	call	nt_cell
	pop	bc
	pop	hl
31$:	inc	hl
	inc	b
	ld	a,b
	cp	#6
	jr	c,30$
dv_next:
	ld	a,(dv_tc)
	inc	a
	ld	(dv_tc),a
	ld	hl,#dv_end
	cp	(hl)
	jp	c,dv_loop
	ret

; A = want (0 sky / 1 wall), B = r ; uses dv_tc
nt_cell:
	ld	c,a
	xor	a
	ld	(nt_hi),a
	ld	a,c
	or	a
	jr	z,40$
	ld	a,(dv_tc)
	ld	c,a
	add	a,a
	add	a,c
	add	a,a
	add	a,b
	add	a,#VIEW_BASE
	jr	41$
40$:	ld	a,(dv_tc)		; columns 15/16 carry the divider bar
	sub	#15
	cp	#2
	jr	nc,45$
	ld	c,a
	add	a,a
	add	a,c
	add	a,a			; 0 or 6
	add	a,b
	add	a,#SKYEDGE_LO
	ld	c,a
	ld	a,#1			; tile number >= 256
	ld	(nt_hi),a
	ld	a,c
	jr	41$
45$:	ld	a,b
	add	a,#SKY_BASE
41$:	push	af			; tile
	; top: NT_TOP + r*64 + tc*2
	ld	l,b
	ld	h,#0
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	ld	a,(dv_tc)
	add	a,a
	ld	e,a
	ld	d,#0
	add	hl,de
	push	hl
	ld	de,#NT_TOP
	add	hl,de
	pop	de			; de = r*64 + tc*2
	ld	a,(nt_hi)
	ld	c,a
	pop	af
	push	af
	push	de
	call	nt_write
	pop	de
	; bottom (mirror): NT_BOT - r*64 + tc*2
	ld	a,(dv_tc)
	add	a,a
	ld	l,a
	ld	h,#0
	ld	bc,#NT_BOT
	add	hl,bc
	; subtract r*64 = de - tc*2
	push	hl
	ld	a,(dv_tc)
	add	a,a
	ld	l,a
	ld	h,#0
	ex	de,hl
	or	a
	sbc	hl,de			; r*64
	ex	de,hl
	pop	hl
	or	a
	sbc	hl,de
	ld	a,(nt_hi)
	or	#0x0C			; flip Y + sprite palette
	ld	c,a
	pop	af
	jp	nt_write
