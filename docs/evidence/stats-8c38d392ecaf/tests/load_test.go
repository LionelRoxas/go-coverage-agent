package stats

import (
	"bytes"
	"math"
	"sort"
	"testing"
	"time"
)

func loadAlmostEqual(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > 1e-9 {
			t.Fatalf("value mismatch at index %d: got %v, want %v", i, got[i], want[i])
		}
	}
}

func TestLoadRawData_VariousTypes(t *testing.T) {
	cases := []struct {
		name string
		raw  interface{}
		want []float64
	}{
		{"uint slice", []uint{1, 2, 3}, []float64{1, 2, 3}},
		{"uint8 slice", []uint8{4, 5}, []float64{4, 5}},
		{"bool slice", []bool{true, false, true}, []float64{1, 0, 1}},
		{"int slice", []int{-1, 0, 2}, []float64{-1, 0, 2}},
		{"int64 slice", []int64{7, -8}, []float64{7, -8}},
		{"string slice", []string{"1.5", "foo", "-2"}, []float64{1.5, -2}},
		{"duration slice", []time.Duration{time.Second, time.Millisecond}, []float64{float64(time.Second), float64(time.Millisecond)}},
		{"map[int]int", map[int]int{0: 5, 1: 10}, []float64{5, 10}},
		{"map[int]bool", map[int]bool{0: true, 1: false, 2: true}, []float64{1, 0, 1}},
		{"map[int]string", map[int]string{0: "3.14", 1: "bad"}, []float64{3.14}},
		{"string input", "7 8 abc 9", []float64{7, 8, 9}},
		{"io.Reader input", bytes.NewReader([]byte("10 11\n12 abc")), []float64{10, 11, 12}},
		{"nil input", nil, []float64{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := LoadRawData(tc.raw)
			// Sort both slices to make map order nondeterministic results comparable
			gotSorted := append([]float64(nil), got...)
			wantSorted := append([]float64(nil), tc.want...)
			sort.Float64s(gotSorted)
			sort.Float64s(wantSorted)
			loadAlmostEqual(t, gotSorted, wantSorted)
		})
	}
}

func loadFloatSliceEqual(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	for i := range got {
		if math.Abs(got[i]-want[i]) > 1e-9 {
			t.Fatalf("value mismatch at index %d: got %v, want %v", i, got[i], want[i])
		}
	}
}

func TestLoadRawData_UncoveredCases(t *testing.T) {
	cases := []struct {
		name  string
		input interface{}
		want  []float64
	}{
		{
			name:  "slice_interface",
			input: []interface{}{int(1), uint(2), float64(3.5), string("4.2"), bool(false), time.Duration(5 * time.Second)},
			want:  []float64{1, 2, 3.5, 4.2, 0, float64(5 * time.Second)},
		},
		{name: "slice_uint16", input: []uint16{10, 20}, want: []float64{10, 20}},
		{name: "slice_uint32", input: []uint32{30, 40}, want: []float64{30, 40}},
		{name: "slice_uint64", input: []uint64{50, 60}, want: []float64{50, 60}},
		{name: "slice_int8", input: []int8{-1, 2}, want: []float64{-1, 2}},
		{name: "slice_int16", input: []int16{-3, 4}, want: []float64{-3, 4}},
		{name: "slice_int32", input: []int32{-5, 6}, want: []float64{-5, 6}},
		{name: "slice_float64", input: []float64{7.7, 8.8}, want: []float64{7.7, 8.8}},
		{name: "map_int_int8", input: map[int]int8{0: -1, 1: 2}, want: []float64{-1, 2}},
		{name: "map_int_int16", input: map[int]int16{0: -3, 1: 4}, want: []float64{-3, 4}},
		{name: "map_int_int32", input: map[int]int32{0: -5, 1: 6}, want: []float64{-5, 6}},
		{name: "map_int_int64", input: map[int]int64{0: -7, 1: 8}, want: []float64{-7, 8}},
		{name: "map_int_uint", input: map[int]uint{0: 9, 1: 10}, want: []float64{9, 10}},
		{name: "map_int_uint8", input: map[int]uint8{0: 11, 1: 12}, want: []float64{11, 12}},
		{name: "map_int_uint16", input: map[int]uint16{0: 13, 1: 14}, want: []float64{13, 14}},
		{name: "map_int_uint32", input: map[int]uint32{0: 15, 1: 16}, want: []float64{15, 16}},
		{name: "map_int_uint64", input: map[int]uint64{0: 17, 1: 18}, want: []float64{17, 18}},
		{name: "map_int_float64", input: map[int]float64{0: 19.9, 1: 20.1}, want: []float64{19.9, 20.1}},
		{name: "map_int_timeDuration", input: map[int]time.Duration{0: 21 * time.Second, 1: 22 * time.Second}, want: []float64{float64(21 * time.Second), float64(22 * time.Second)}},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := LoadRawData(tc.input)
			loadFloatSliceEqual(t, []float64(got), tc.want)
		})
	}
}
