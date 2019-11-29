#include "Python.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/file.h>
#include <math.h>

#define OUTBUFFERSIZE 1048576
#define MAXLOGLINESIZE 100

// spi packet fields
#define HEADER 			0xE0000000
#define SUBHEADER 		0xFC000000
#define TIMESLOT_TR		0x1FFFFF00
#define TIMESLOT_ADC		0x03FFFFE0
#define SECOND_FS			0x01FFFF00
#define SECOND_ADC		0x03FFFE00
#define SAMPLE_ADC		0x03FFFFFC
#define PINLEVEL			0x000000FF
// packet headers
#define HD_TRACING			0x00000000
#define HD_FULLSEC			0x20000000
#define HD_RST					0x40000000
#define HD_RST_FULLSEC		0x60000000
#define HD_FIFO 				0x80000000
#define HD_FIFO_FULLSEC		0xA0000000
#define HD_FIFO_RST			0xC0000000
#define HD_ADC					0xE0000000
// packet subheaders
#define SUB_FIRST_SAMPLE	0xE0000000
#define SUB_LAST_SAMPLE		0xE4000000
#define SUB_INTERVAL			0xE8000000
#define SUB_SECOND_CNT		0xEC000000
#define SUB_SAMPLE			0xF0000000
#define SUB_ERROR				0xFC000000
// spi packet data field offsets (i.e. how much shifting)
#define OFF_ADC_SAMPLE		2
#define OFF_TIMESLOT			8
#define OFF_ADC_SECOND		9
#define OFF_SECOND			8
#define OFF_ADC_TIMESLOT	5
// FPGA internals
#define FULLSEC_MAX (24*3600 + 1)
#define SEC_PART_MAX 2000000
#define ADC_FILTER_DELAY_US (39 * 35.759)


const char* pinnames[8] = {"RST", "SIG2", "SIG1", "INT2", "INT1", "LED3", "LED2", "LED1"};
const int pinnumbers[8] = {60   , 74    , 75    , 87    , 113   , 69    , 70    , 71};

static PyObject *cResultfetcherError;

struct obs_timeval {
	int32_t tv_sec;
	int32_t tv_usec;
};


static PyObject *cresultfetcher_getppresults(PyObject *self, PyObject *args, PyObject *keywds){
	int obsid, nodeid, len;
	char *obsdbfilepath, *testresultfilepath;
	uint32_t packet_size, i, sample_count, header_size, w;
	int32_t value;
	struct obs_timeval sampling_start, sampling_end;
	double packet_end, timestamp, step, sampletimestamp;
	double conv_value, calib_factor, calib_offset;
	double avg = 0;
	int count = 0;
	char *outstr, *write_ptr;
	FILE *obsdbfile;
	int testresultfile_fd;
	PyObject *values_list, *timestamps_list, *allvalues_list, *alltimestamps_list;
	PyObject *ret_list = NULL;
	static char *kwlist[] = {"obsid", "nodeid", "obsdbfilepath", "resultfilepath", "slotcalib_factor", "slotcalib_offset", NULL};

	if (!PyArg_ParseTupleAndKeywords(args, keywds, "iissdd", kwlist, &obsid, &nodeid, &obsdbfilepath, &testresultfilepath, &calib_factor, &calib_offset))
		return ret_list;

	outstr = malloc(OUTBUFFERSIZE);
	if (outstr == NULL)
		return ret_list;
	write_ptr = outstr;
	
	// Open files:
	obsdbfile = fopen(obsdbfilepath, "r");
	testresultfile_fd = open(testresultfilepath, O_WRONLY | O_APPEND);

	// Create a list for returning the values to Python (needed for vizualisation):
	ret_list = PyList_New(4);
	alltimestamps_list = PyList_New(0);
	allvalues_list = PyList_New(0);

	// Read the DB file, parse and convert it:
	while (!feof(obsdbfile)) {
		header_size = 0;
		// First read the size of the next packet:
		header_size+=fread(&packet_size, sizeof(packet_size), 1, obsdbfile);
		// Now read the packet:
		header_size+=fread(&(sampling_start.tv_sec), 4, 1, obsdbfile);
		header_size+=fread(&(sampling_start.tv_usec), 4, 1, obsdbfile);
		header_size+=fread(&(sampling_end.tv_sec), 4, 1, obsdbfile);
		header_size+=fread(&(sampling_end.tv_usec), 4, 1, obsdbfile);
		header_size+=fread(&sample_count, 4, 1, obsdbfile);
		if (header_size != 6)
			break;
		// Calculate sampling step and initial timestamp:
		timestamp = (double) sampling_start.tv_sec + (((double)sampling_start.tv_usec)/1000000);
		packet_end = (double) sampling_end.tv_sec + (((double)sampling_end.tv_usec)/1000000);
		if (sample_count == 1) {
			// There is no step since there is only one sample.
			step = 0;
		} else {
			step = (packet_end - timestamp) / (sample_count - 1); // timestamp is time of first sample, packet_end is time of last sample_count
		}

		// Make lists for values and timestamps of this entry:
		values_list = PyList_New(sample_count);
		timestamps_list = PyList_New(sample_count);

		// Parse the packet:
		for (i=0;i<sample_count;i++) {
			// Get value:
			if ( fread(&value, sizeof(value), 1, obsdbfile) == 1 ) {
				// Convert value:
				if (value == 0x800000) {
					conv_value = 9999.0;
				} else {
					if (value & 0x800000) {
						*((char*)&value + 3) = 0xff; // sign extend 24 -> 32 bit
					}
					conv_value = ((value * 19.868217294) / 1e6) * calib_factor + calib_offset;
				}
				// Calculate timestamp:
				sampletimestamp = timestamp + i * step;
				// DEBUG printf("timestamp: %f\tpacket_end: %f\tstep:%f\tsample_count:%d\ti:%d\tsampletimestamp:%f\n",timestamp, packet_end, step, sample_count,i,sampletimestamp);

				// Insert the values into the python lists:
				PyList_SET_ITEM(timestamps_list, i, Py_BuildValue("d", sampletimestamp));
				PyList_SET_ITEM(values_list, i, Py_BuildValue("d", conv_value));

				// Prepare the output string:				
				len = sprintf(write_ptr, "%.6f,%d,%d,%.6f\n", sampletimestamp, obsid, nodeid, conv_value);
				write_ptr+=len;

				// Write buffered values to the file:
				if (write_ptr - outstr > OUTBUFFERSIZE - MAXLOGLINESIZE) {
					flock(testresultfile_fd, LOCK_EX);
					w = write(testresultfile_fd, outstr, write_ptr - outstr);
					flock(testresultfile_fd, LOCK_UN);
					write_ptr = outstr;
				}
				
				// update stats
				avg = (double)(count) / (double)(count + 1) * avg + conv_value / (double)(count + 1);
				count++;

			}
			else {
				// The element could not be read, thus insert dummy values into the python lists:
				PyList_SET_ITEM(timestamps_list, i, Py_BuildValue(""));
				PyList_SET_ITEM(values_list, i, Py_BuildValue(""));
			}

		}

		// Insert the lists into the higher up lists:
		PyList_Append(alltimestamps_list, timestamps_list);
		Py_DECREF(timestamps_list);
		PyList_Append(allvalues_list, values_list);
		Py_DECREF(values_list);

	}
	// Write trailing values to the file:
	if (write_ptr - outstr > 0) {
		flock(testresultfile_fd, LOCK_EX);
		w = write(testresultfile_fd, outstr, write_ptr - outstr);
		flock(testresultfile_fd, LOCK_UN);
	}

	free(outstr);
	
	// Close files
	close(testresultfile_fd);
	fclose(obsdbfile);

	// Prepare List to return to Python:
	PyList_SET_ITEM(ret_list, 0, alltimestamps_list);
	PyList_SET_ITEM(ret_list, 1, allvalues_list);
	PyList_SET_ITEM(ret_list, 2, Py_BuildValue("d", avg));
	PyList_SET_ITEM(ret_list, 3, Py_BuildValue("i", count));

	return ret_list;
} // END resultfetcher_getppresults

/**
 * cresultfetcher_getdaqresults: converts the 32bit adc packets to flocklab testresults (tracing, actuation, powerprof and errors) 
 **/

#define log_error(epoch, timeslot, msg, ...) do{\
	fprintf(error_fd, "%d.%07d,%d,%d, " msg "\n", epoch, timeslot * 5, obsid, nodeid, __VA_ARGS__); \
} while (0);

static PyObject *cresultfetcher_getdaqresults(PyObject *self, PyObject *args, PyObject *keywds){
	int obsid, nodeid, len;
	// FILE stuff
	char *obsdbfilepath, *tracing_testresultfilepath, *powerprof_testresultfilepath, *errorlog_testresultfilepath, *actuation_testresultfilepath;
	// DB stuff
	uint32_t packet_size, i, r, spi_packet, w;
	//ADC stuff
	int32_t value;
	int32_t sample_list[101] = {};
	uint8_t sample_cnt = 0, excess_sample_cnt = 0;
	uint8_t j;
	uint32_t pp_start_sec, pp_start_500ns, pp_end_500ns, tmp_500ns;
	int32_t tmp_sec;
	double pp_step;
	double conv_value, calib_factor, calib_offset;
	char* sample_str;
	double avg = 0;
	int count = 0;
	// TRACING stuff
	uint32_t timestamp_500nsec;
	uint32_t timeslot;
	uint8_t pin_level;
	uint8_t pin_level_old = 1;
	int pin_level_prev;
	uint8_t pinmask;
// 	char* pin_name;
	// TIME stuff
	int t_current_second, p_current_second;
	int tmp_second;
	char* event_time;
	int start_test_epoch;
	int stop_test_epoch;
	
	// python return stuff
	PyObject *values_list, *timestamps_list, *allvalues_list, *alltimestamps_list, *tracing_list;
	PyObject *ret_list = NULL;
	PyObject *py_sample_list = NULL;
	PyObject *py_sample = NULL;
	
	// MORE FILE stuff
	FILE *obsdbfile;
	FILE *error_fd;
	int fd, tracing_fd, actuation_fd, powerprof_fd;
//     PyObject *values_list, *timestamps_list, *allvalues_list, *alltimestamps_list;
	static char *kwlist[] = {"obsid", "nodeid", "obsdbfilepath", "tracingresults", "actuationresults", "powerprofresults", "errorlog", "slotcalib_factor", "slotcalib_offset", "start_test_epoch", "stop_test_epoch", "pin_level_prev", "p_sample_list","p_current_second", "pp_start_sec", "p_start_500ns","t_current_second", NULL};

	if (!PyArg_ParseTupleAndKeywords(args, keywds, "iisssssddiiiOiiii", kwlist, &obsid, &nodeid, &obsdbfilepath, &tracing_testresultfilepath, &actuation_testresultfilepath, &powerprof_testresultfilepath, &errorlog_testresultfilepath ,&calib_factor, &calib_offset, &start_test_epoch, &stop_test_epoch, &pin_level_prev,
		&py_sample_list, &p_current_second, &pp_start_sec, &pp_start_500ns, &t_current_second))
		return ret_list;

	// Open files:
	obsdbfile = fopen(obsdbfilepath, "r");
	tracing_fd = open(tracing_testresultfilepath, O_WRONLY | O_APPEND);
	if(tracing_fd < 0){
		printf("error opening tracing result file\n");
	}
	actuation_fd = open(actuation_testresultfilepath, O_WRONLY | O_APPEND);
	if(actuation_fd < 0){
		printf("error opening tracing result file\n");
	}
	powerprof_fd = open(powerprof_testresultfilepath, O_WRONLY | O_APPEND);
	if(powerprof_fd < 0){
		printf("error opening powerprof result file\n");
	}
	error_fd = fopen(errorlog_testresultfilepath, "a");
	if(error_fd == NULL){
		printf("error opening error log file\n");
	}
	
	ret_list = PyList_New(11);
	alltimestamps_list = PyList_New(0);
	allvalues_list = PyList_New(0);
	tracing_list = PyList_New(0);
	
	// alloc some memory and initialize timing related vars
	event_time = malloc(200 * sizeof(unsigned char));
	sample_str = malloc(200 * sizeof(unsigned char));
	pin_level_old = (uint8_t)pin_level_prev;
	printf("start, p_current_second=%d, pp_start_500ns=%d, t_current_second=%d\n", p_current_second, pp_start_500ns, t_current_second);
	printf("sample_cnt=%d\n", (int)PyTuple_Size(py_sample_list));
	
	sample_cnt = (int)PyTuple_Size(py_sample_list);
	for (j=0;j<sample_cnt;j++) {
		if (j < sizeof(sample_list) / sizeof(sample_list[0])) {
			py_sample = PyTuple_GetItem(py_sample_list, j);
			PyArg_Parse(py_sample, "i", &sample_list[j]);
		}
		else {
			excess_sample_cnt++;
		}
	}
	
	while (!feof(obsdbfile)) {
		// First read the size of the next packet:
		r = fread(&packet_size, sizeof(packet_size), 1, obsdbfile);
		if(r != 1)
			// error reading number of packets
			break;
		// get packets (4bytes) according to the number in packet_size
		for(i = 0; i < (packet_size / sizeof(spi_packet)); i++){
			r = fread(&spi_packet, sizeof(spi_packet), 1, obsdbfile);
			if(r != 1){
				// error reading spi_packet
				break;
			}
			// take the spi_packet apart
			// 1) check the header
			switch(spi_packet & HEADER){
				case HD_FULLSEC:
				case HD_TRACING:
					if((spi_packet & HEADER) == HD_FULLSEC) {
						tmp_second = (spi_packet & SECOND_FS) >> OFF_SECOND;
						if ((t_current_second % FULLSEC_MAX) > tmp_second)
							t_current_second += FULLSEC_MAX;
						t_current_second = (t_current_second / FULLSEC_MAX) * FULLSEC_MAX + tmp_second;
// 						printf("t_current_second %d\n", t_current_second);
						timeslot = 0;
						pin_level = spi_packet & PINLEVEL;
					}
					else {
						timeslot = (spi_packet & TIMESLOT_TR) >> OFF_TIMESLOT;
						pin_level = spi_packet & PINLEVEL;
					}
					if(t_current_second >= 0){
						// timestamp_500nsec defines the offset to the current full_second count of the event with a 500ns resolution
						timestamp_500nsec = timeslot;
						pinmask = pin_level_old ^ pin_level; // get level changes
						if (pinmask == 0 && ((spi_packet & HEADER) != HD_FULLSEC)) {
							log_error(start_test_epoch + t_current_second / 5, ((spi_packet & TIMESLOT_TR) >> OFF_TIMESLOT), "Missing tracing events: PinLevels(hex) : 0x%x", pin_level);
// 							printf("WARNING: empty pin mask. Levels 0x%x, time %d.%07d\n", pin_level, start_test_epoch + t_current_second / 5, (t_current_second % 5) * SEC_PART_MAX + timestamp_500nsec);
                        }
						for(j = 0; j < 8; j++){
							if((pinmask >> j) & 0x01){
								if(j >= 3){
									fd = tracing_fd;
									len = sprintf(event_time, "%d.%07d,%d,%d,%s,%d\n", start_test_epoch + t_current_second / 5, (t_current_second % 5) * SEC_PART_MAX + timestamp_500nsec,obsid,nodeid, pinnames[j], (pin_level >> j) & 1);
									PyObject * tpl = Py_BuildValue("iid", pinnumbers[j], (pin_level >> j) & 1, (double)(start_test_epoch + t_current_second / 5 + ((t_current_second % 5) * SEC_PART_MAX + timestamp_500nsec) * 1e-7));
									PyList_Append(tracing_list, tpl);
									Py_DECREF(tpl);
								} else {
									fd = actuation_fd;
									len = sprintf(event_time, "%d.%07d,%d.%07d,%d,%d,%s,%d\n", start_test_epoch + t_current_second / 5, (t_current_second % 5) * SEC_PART_MAX + timestamp_500nsec, start_test_epoch + t_current_second / 5, (t_current_second % 5) * SEC_PART_MAX + timestamp_500nsec, obsid, nodeid, pinnames[j], (pin_level >> j) & 1);
								}
								w = write(fd, event_time, len);
								if(!w)
									printf("error writing pin name and level\n");
							}
						}
						pin_level_old = pin_level;
					}
					break;
				case HD_RST:
					log_error(start_test_epoch + t_current_second / 5, ((spi_packet & TIMESLOT_TR) >> OFF_TIMESLOT), "Hard Reset: PinLevels(hex) : 0x%x", (spi_packet & PINLEVEL)); break;
				case HD_RST_FULLSEC:
					log_error(start_test_epoch + t_current_second / 5, ((spi_packet & TIMESLOT_TR) >> OFF_TIMESLOT), "Hard Reset and Full Second: PinLevels(hex) : 0x%x", (spi_packet & PINLEVEL));
					break;
				case HD_FIFO:
					log_error(start_test_epoch + t_current_second / 5, ((spi_packet & TIMESLOT_TR) >> OFF_TIMESLOT), "FIFO Full: PinLevels(hex) : 0x%x", (spi_packet & PINLEVEL));
					break;
				case HD_FIFO_FULLSEC:
					log_error(start_test_epoch + t_current_second / 5, ((spi_packet & TIMESLOT_TR) >> OFF_TIMESLOT), "FIFO Full and Full Second: PinLevels(hex) : 0x%x", (spi_packet & PINLEVEL));
					break;
				case HD_FIFO_RST:
					log_error(start_test_epoch + t_current_second / 5, ((spi_packet & TIMESLOT_TR) >> OFF_TIMESLOT), "FIFO Full and Hard Reset: PinLevels(hex) : 0x%x", (spi_packet & PINLEVEL));
					break;
				case HD_ADC:
					// adc package
					switch(spi_packet & SUBHEADER){
						case SUB_FIRST_SAMPLE:
							pp_start_500ns = (spi_packet & TIMESLOT_ADC) >> OFF_ADC_TIMESLOT;
							pp_start_sec = p_current_second;
							break;
						case SUB_LAST_SAMPLE:
						case SUB_INTERVAL:
							pp_end_500ns = (spi_packet & TIMESLOT_ADC) >> OFF_ADC_TIMESLOT;
							if ((spi_packet & SUBHEADER) == SUB_LAST_SAMPLE)
								pp_step = ((double)((p_current_second - pp_start_sec)* SEC_PART_MAX + (pp_end_500ns - pp_start_500ns)))/((double)(sample_cnt-1));
							else
								pp_step = ((double)((p_current_second - pp_start_sec)* SEC_PART_MAX + (pp_end_500ns - pp_start_500ns)))/((double)(sample_cnt));
 							printf("p_samples from %d %d to %d %d, step %f us\n", pp_start_sec, pp_start_500ns, p_current_second, pp_end_500ns, pp_step / 10);
							// create list for return to fetcher script
							values_list = PyList_New(sample_cnt);
							timestamps_list = PyList_New(sample_cnt);
							for(j = 0; j < sample_cnt; j++){
								tmp_sec =  pp_start_sec / 5 + ((pp_start_sec % 5) * SEC_PART_MAX + pp_start_500ns + j*pp_step - ADC_FILTER_DELAY_US * 10)/1e7;
								if (tmp_sec < 0) {
									printf("sample before start\n");
									continue;
								}
								tmp_500ns =              (int)((pp_start_sec % 5) * SEC_PART_MAX + pp_start_500ns + j*pp_step) % (uint32_t)1e7;
								if (tmp_500ns <  ADC_FILTER_DELAY_US * 10)
									tmp_500ns+=1e7 - ADC_FILTER_DELAY_US * 10;
								else
									tmp_500ns-=ADC_FILTER_DELAY_US * 10;
								if (sample_list[j] == 0x800000) {
									conv_value = 9999.0;
								} else {
									if (sample_list[j] & 0x800000) {
										*((char*)&sample_list[j] + 3) = 0xff; // sign extend 24 -> 32 bit
									}									
								conv_value = (((int)sample_list[j] * 19.868217294) / 1e6) * calib_factor + calib_offset;
								}
								// append values to python list
								PyList_SET_ITEM(timestamps_list, j, Py_BuildValue("d", (double)(start_test_epoch + tmp_sec + tmp_500ns*1e-7)));
								PyList_SET_ITEM(values_list, j, Py_BuildValue("d", conv_value));
								// write to result file
								len = sprintf(sample_str, "%d.%07d,%d,%d,%.8f\n", start_test_epoch + tmp_sec, tmp_500ns, obsid, nodeid, conv_value);
								w = write(powerprof_fd, sample_str, len);
								if(!w)
									printf("error writing adc sample\n");
								avg = (double)(count) / (double)(count + 1) * avg + conv_value / (double)(count + 1);
								count++;								
							}
							if (excess_sample_cnt > 0) {
								log_error(start_test_epoch + p_current_second, ((spi_packet & TIMESLOT_ADC) >> OFF_ADC_TIMESLOT), "%d excess ADC samples", excess_sample_cnt);
								printf("Warning: Excess sample count is %d\n", excess_sample_cnt);
							}
							// append temporary lists to main lists
							PyList_Append(alltimestamps_list, timestamps_list);
							Py_DECREF(timestamps_list);
							PyList_Append(allvalues_list, values_list);
							Py_DECREF(values_list);
							pp_start_sec = p_current_second;
							pp_start_500ns = pp_end_500ns;
							sample_cnt = 0;
							excess_sample_cnt = 0;
							break;
						case SUB_SECOND_CNT:
							tmp_second = (spi_packet & SECOND_ADC) >> OFF_ADC_SECOND;
							if ((p_current_second % FULLSEC_MAX) > tmp_second)
								p_current_second += FULLSEC_MAX;
							p_current_second = (p_current_second / FULLSEC_MAX) * FULLSEC_MAX + tmp_second;
// 							printf("pp_sec %d\n", p_current_second);
							break;
						case SUB_SAMPLE:
							value = (spi_packet & SAMPLE_ADC) >> OFF_ADC_SAMPLE;
							// save the current value to a array of samples
							if (sample_cnt < sizeof(sample_list) / sizeof(sample_list[0])) {
								sample_list[sample_cnt] = value;
								sample_cnt++;
							}
							else {
								excess_sample_cnt++;
							}
							break;
						default:
							break;
					}
					break;
				default:
					printf("unknown header for packet %d", spi_packet);
					break;
			}
		}
	}
	printf("done\n");
	free(event_time);
	free(sample_str);
	fclose(obsdbfile);
	close(powerprof_fd);
	close(tracing_fd);
	close(actuation_fd);
	fclose(error_fd);
	printf("closed\n");
	// prepare pp state
	py_sample_list = PyTuple_New(sample_cnt);
	for (j=0;j<sample_cnt;j++) {
		PyTuple_SetItem(py_sample_list, j, Py_BuildValue("i", sample_list[j]));
	}
	PyList_SET_ITEM(ret_list, 0, alltimestamps_list);
	PyList_SET_ITEM(ret_list, 1, allvalues_list);
	PyList_SET_ITEM(ret_list, 2, tracing_list);
	PyList_SET_ITEM(ret_list, 3, Py_BuildValue("d", avg));
	PyList_SET_ITEM(ret_list, 4, Py_BuildValue("i", count));
	PyList_SET_ITEM(ret_list, 5, Py_BuildValue("i", (int)pin_level_old));
	PyList_SET_ITEM(ret_list, 6, py_sample_list);
	PyList_SET_ITEM(ret_list, 7, Py_BuildValue("i", p_current_second));
	PyList_SET_ITEM(ret_list, 8, Py_BuildValue("i", pp_start_sec));
	PyList_SET_ITEM(ret_list, 9, Py_BuildValue("i", pp_start_500ns));
	PyList_SET_ITEM(ret_list,10, Py_BuildValue("i", t_current_second));
	
	return ret_list;
} // END cresultfetcher_getdaqresults



static PyMethodDef cResultfetcherMethods[] = {
	{"getppresults", (PyCFunction) cresultfetcher_getppresults, METH_VARARGS | METH_KEYWORDS, "Fetch powerprofiling results."},
	{"getdaqresults", (PyCFunction) cresultfetcher_getdaqresults, METH_VARARGS | METH_KEYWORDS, "Fetch flockdaq results."},
	{NULL, NULL, 0, NULL}
};

/*
 * WORKS WITH PYTHON2.x only
PyMODINIT_FUNC initcResultfetcher(void){
	PyObject *m;

	m = Py_InitModule("cResultfetcher", cResultfetcherMethods);
	if (m == NULL)
		return;

	cResultfetcherError = PyErr_NewException("cresultfetcher.error", NULL, NULL);
	Py_INCREF(cResultfetcherError);
	PyModule_AddObject(m, "error", cResultfetcherError);
} // END initresultfetcher
*/

PyMODINIT_FUNC PyInit_cResultfetcher(void)
{
    static struct PyModuleDef pyModResultfetcher =
    {
        PyModuleDef_HEAD_INIT,
        "cResultfetcher", /* name of module */
        "",               /* module documentation, may be NULL */
        -1,               /* size of per-interpreter state of the module, or -1 if the module keeps state in global variables. */
        cResultfetcherMethods
    };
	PyObject *m = PyModule_Create(&pyModResultfetcher);
	if (m)
	{
		cResultfetcherError = PyErr_NewException("cresultfetcher.error", NULL, NULL);
		Py_INCREF(cResultfetcherError);
		PyModule_AddObject(m, "error", cResultfetcherError);
    }
	return m;
}
